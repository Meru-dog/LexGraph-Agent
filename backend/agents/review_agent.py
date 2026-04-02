"""LangGraph Contract Review Agent.

Graph topology:
    START → parser → clause_classifier → review_loop
          → cross_ref_checker
          → statute_checker
          → human_checkpoint (interrupt)
          → redline_generator → END
"""

from langchain_core.messages import HumanMessage

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import ContractReviewState, Clause, ClauseReview, ComplianceFlag
from tools.clause_segmenter import clause_segmenter
from tools.graph_search import graph_search
from tools.statute_lookup import statute_lookup
from tools.cross_reference_checker import cross_reference_checker
from tools.report_formatter import report_formatter
from models.model_factory import get_llm
from models.langchain_message_text import extract_message_text


def parser(state: ContractReviewState) -> dict:
    """Segment raw contract text into typed clauses."""
    clauses = clause_segmenter(
        text=state["raw_contract"],
        contract_type=state["contract_type"],
    )
    return {"clauses": clauses}


def clause_classifier(state: ContractReviewState) -> dict:
    """Map each clause to its semantic type using LLM classifier.
    In Phase 2 this is a pass-through; Phase 3 integrates LLM."""
    return {"clauses": state["clauses"]}


def review_loop(state: ContractReviewState) -> dict:
    """Per-clause risk scoring, issue identification, redline suggestions."""
    reviews: list[ClauseReview] = []
    model_name = state.get("model_name", "ollama")
    for clause in state["clauses"]:
        graph_results = graph_search(
            query=clause["text"][:200],
            jurisdiction=state["jurisdiction"],
            node_types=["Statute", "Case", "LegalConcept"],
        )
        risk = _score_clause_risk(clause, state["jurisdiction"], model_name)
        issues = _identify_issues(clause, state["jurisdiction"], model_name)
        redline = _generate_redline(clause, state["jurisdiction"], model_name)
        reason = _generate_redline_reason(clause, issues, state["jurisdiction"], model_name)
        reviews.append(
            ClauseReview(
                clause_id=clause["id"],
                risk_level=risk,
                issues=issues,
                redline_suggestion=redline,
                redline_reason=reason,
                text_snippet=clause["text"][:120],
                applicable_statutes=[
                    n.get("title", "") for n in graph_results.get("nodes", [])[:2]
                ],
                citations=[n.get("node_id", "") for n in graph_results.get("nodes", [])[:3]],
            )
        )
    return {"clause_reviews": reviews}


def cross_ref_checker(state: ContractReviewState) -> dict:
    """Detect internal inconsistencies across clauses."""
    inconsistencies = cross_reference_checker(state["clauses"])
    return {"inconsistencies": inconsistencies}


def statute_checker(state: ContractReviewState) -> dict:
    """Validate each clause against Neo4j statute graph."""
    flags: list[ComplianceFlag] = []
    for review in state["clause_reviews"]:
        if review["risk_level"] in ("critical", "high"):
            for statute_ref in review["applicable_statutes"]:
                provision = statute_lookup(
                    article_ref=statute_ref,
                    jurisdiction=state["jurisdiction"],
                )
                if provision:
                    flags.append(
                        ComplianceFlag(
                            clause_id=review["clause_id"],
                            statute=statute_ref,
                            issue=f"Potential non-compliance with {statute_ref}",
                            severity=review["risk_level"],
                        )
                    )
    return {"compliance_flags": flags}


def human_checkpoint(state: ContractReviewState) -> dict:
    """Pass-through — attorney review via the /approve endpoint after completion."""
    return {}


def redline_generator(state: ContractReviewState) -> dict:
    """Build the final redlined contract and review report.

    Priority: attorney manual redlines override AI suggestions.
    For clauses without an attorney redline, the AI redline_suggestion is applied.
    """
    redlined = state["raw_contract"]
    attorney_redlines = state.get("attorney_redlines", {}) or {}

    for review in state["clause_reviews"]:
        clause = next((c for c in state["clauses"] if c["id"] == review["clause_id"]), None)
        if not clause:
            continue
        replacement = attorney_redlines.get(review["clause_id"]) or review.get("redline_suggestion", "")
        if replacement and replacement != clause["text"]:
            redlined = redlined.replace(clause["text"], replacement)

    report = report_formatter(
        findings=[
            {
                "status": r["risk_level"],
                "text": f"{r['clause_id']}: {', '.join(r['issues'])}",
                "section": r["clause_id"],
                "citations": r["citations"],
            }
            for r in state["clause_reviews"]
        ],
        template="contract_review",
    )
    return {"redlined_contract": redlined, "review_report": report}


# ─── Internal helpers (mock implementations for Phase 2) ──────────────────────

def _score_clause_risk(clause: Clause, jurisdiction: str, model_name: str = "ollama") -> str:
    """Score clause risk via LLM, fallback to rule-based."""
    try:
        llm = get_llm(f"You are a contract lawyer in {jurisdiction} jurisdiction. Respond with one word only.", model_name, thinking=False)
        prompt = (
            f"Rate the legal risk of this contract clause as exactly one word "
            f"(critical, high, medium, or low).\n\nClause: {clause['text'][:500]}\n\nRisk level:"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        level = extract_message_text(response).strip().lower().split()[0]
        if level in ("critical", "high", "medium", "low"):
            return level
    except Exception:
        pass
    risk_map = {"ip": "high", "termination": "medium", "liability": "medium", "payment": "ok"}
    return risk_map.get(clause.get("type", ""), "low")


def _identify_issues(clause: Clause, jurisdiction: str, model_name: str = "ollama") -> list[str]:
    """Identify legal issues in a clause via LLM, fallback to rule-based."""
    try:
        llm = get_llm(f"You are a contract lawyer in {jurisdiction} jurisdiction. List issues concisely, one per line.", model_name, thinking=True)
        prompt = (
            f"List up to 3 specific legal issues with this contract clause. "
            f"One issue per line, no bullets, no preamble:\n\n"
            f"Clause: {clause['text'][:600]}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        issues = [line.strip() for line in extract_message_text(response).strip().split("\n") if line.strip()]
        return issues[:3]
    except Exception:
        pass
    issues_map = {
        "ip": ["IP ownership vests in Service Provider — unfavourable for Client"],
        "termination": ["Short notice period (30 days) — consider extending to 60 days"],
        "liability": ["Liability cap limited to 3 months — consider 12 months"],
    }
    return issues_map.get(clause.get("type", ""), [])


_REDLINE_PREAMBLES = [
    "here is the rewritten clause:",
    "here's the rewritten clause:",
    "rewritten clause:",
    "revised clause:",
    "modified clause:",
    "updated clause:",
    "here is my rewrite:",
    "here is the revised clause:",
    "here is the modified clause:",
    "rewrite:",
]


def _generate_redline(clause: Clause, jurisdiction: str, model_name: str = "ollama") -> str:
    """Generate a redlined version of the clause via LLM.

    Returns ONLY the rewritten clause text — no preambles or explanations.
    """
    try:
        llm = get_llm(
            f"You are a senior contract lawyer in {jurisdiction} jurisdiction "
            f"representing the client (buyer/licensee). "
            f"Output ONLY the rewritten clause text. Never include explanations, preambles, or commentary.",
            model_name,
            thinking=True,
        )
        prompt = (
            f"Rewrite this contract clause to better protect the client's interests. "
            f"OUTPUT ONLY the rewritten clause text. "
            f"Do NOT include any preamble, heading, explanation, commentary, or notes. "
            f"Start directly with the rewritten clause text:\n\n{clause['text']}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        text = extract_message_text(response).strip()

        # Strip common Gemini preambles (case-insensitive)
        lower = text.lower()
        for preamble in _REDLINE_PREAMBLES:
            if lower.startswith(preamble):
                text = text[len(preamble):].lstrip("\n ").strip()
                break

        # If response is empty or suspiciously short, return original
        if not text or len(text) < 10:
            return clause["text"]

        return text
    except Exception:
        return clause["text"]  # Return original unchanged — don't pollute the diff


def _generate_redline_reason(clause: Clause, issues: list[str], jurisdiction: str, model_name: str = "ollama") -> str:
    """Generate a one-sentence reason explaining why this specific clause was rewritten."""
    if not issues:
        return f"Clause rewritten to improve client protections under {jurisdiction} law."
    try:
        llm = get_llm(
            f"You are a senior contract lawyer in {jurisdiction} jurisdiction. "
            f"Explain redline changes concisely.",
            model_name,
            thinking=False,
        )
        issues_text = "; ".join(issues[:2])
        prompt = (
            f"In ONE sentence, explain why this contract clause was rewritten. "
            f"Clause type: {clause.get('type', 'general')}. "
            f"Identified issues: {issues_text}. "
            f"Start with 'Rewritten to...' or 'Modified to...'"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        reason = extract_message_text(response).strip()
        # Ensure single sentence
        reason = reason.split("\n")[0].split(". ")[0]
        if reason and not reason.endswith("."):
            reason += "."
        return reason if reason else f"Rewritten to address: {issues_text}."
    except Exception:
        return f"Rewritten to address: {'; '.join(issues[:2])}." if issues else ""


# ─── Graph construction ────────────────────────────────────────────────────────

def build_review_graph() -> StateGraph:
    builder = StateGraph(ContractReviewState)

    builder.add_node("parser", parser)
    builder.add_node("clause_classifier", clause_classifier)
    builder.add_node("review_loop", review_loop)
    builder.add_node("cross_ref_checker", cross_ref_checker)
    builder.add_node("statute_checker", statute_checker)
    builder.add_node("human_checkpoint", human_checkpoint)
    builder.add_node("redline_generator", redline_generator)

    builder.add_edge(START, "parser")
    builder.add_edge("parser", "clause_classifier")
    builder.add_edge("clause_classifier", "review_loop")
    builder.add_edge("review_loop", "cross_ref_checker")
    builder.add_edge("cross_ref_checker", "statute_checker")
    builder.add_edge("statute_checker", "human_checkpoint")
    builder.add_edge("human_checkpoint", "redline_generator")
    builder.add_edge("redline_generator", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


review_graph = build_review_graph()
