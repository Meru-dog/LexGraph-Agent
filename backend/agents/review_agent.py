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
from models.gemini_lc import get_llm


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
    for clause in state["clauses"]:
        graph_results = graph_search(
            query=clause["text"][:200],
            jurisdiction=state["jurisdiction"],
            node_types=["Statute", "Case", "LegalConcept"],
        )
        risk = _score_clause_risk(clause, state["jurisdiction"])
        reviews.append(
            ClauseReview(
                clause_id=clause["id"],
                risk_level=risk,
                issues=_identify_issues(clause, state["jurisdiction"]),
                redline_suggestion=_generate_redline(clause, state["jurisdiction"]),
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
    """LangGraph interrupt — attorney reviews high-risk clauses."""
    from langgraph.types import interrupt
    high_risk = [r for r in state["clause_reviews"] if r["risk_level"] in ("critical", "high")]
    review = interrupt(
        {
            "reason": "Attorney review required for high-risk clauses.",
            "high_risk_clauses": [r["clause_id"] for r in high_risk],
        }
    )
    return {
        "attorney_redlines": review.get("redlines", {}),
        "approved_clauses": review.get("approved", []),
    }


def redline_generator(state: ContractReviewState) -> dict:
    """Build the final redlined contract and review report."""
    redlined = state["raw_contract"]
    for clause_id, attorney_text in state.get("attorney_redlines", {}).items():
        clause = next((c for c in state["clauses"] if c["id"] == clause_id), None)
        if clause:
            redlined = redlined.replace(clause["text"], attorney_text)

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

def _score_clause_risk(clause: Clause, jurisdiction: str) -> str:
    """Score clause risk via Gemini, fallback to rule-based."""
    try:
        llm = get_llm(f"You are a contract lawyer in {jurisdiction} jurisdiction.")
        prompt = (
            f"Rate the legal risk of this contract clause as one word: "
            f"critical, high, medium, or low.\n\nClause: {clause['text'][:500]}\n\nRisk level:"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        level = response.content.strip().lower().split()[0]
        if level in ("critical", "high", "medium", "low"):
            return level
    except Exception:
        pass
    risk_map = {"ip": "high", "termination": "medium", "liability": "medium", "payment": "ok"}
    return risk_map.get(clause.get("type", ""), "low")


def _identify_issues(clause: Clause, jurisdiction: str) -> list[str]:
    """Identify legal issues in a clause via Gemini, fallback to rule-based."""
    try:
        llm = get_llm(f"You are a contract lawyer in {jurisdiction} jurisdiction.")
        prompt = (
            f"List up to 3 specific legal issues with this contract clause (one per line, no bullets):\n\n"
            f"Clause: {clause['text'][:600]}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        issues = [line.strip() for line in response.content.strip().split("\n") if line.strip()]
        return issues[:3]
    except Exception:
        pass
    issues_map = {
        "ip": ["IP ownership vests in Service Provider — unfavourable for Client"],
        "termination": ["Short notice period (30 days) — consider extending to 60 days"],
        "liability": ["Liability cap limited to 3 months — consider 12 months"],
    }
    return issues_map.get(clause.get("type", ""), [])


def _generate_redline(clause: Clause, jurisdiction: str) -> str:
    """Generate a redlined version of the clause via Gemini."""
    try:
        llm = get_llm(
            f"You are a senior contract lawyer in {jurisdiction} jurisdiction "
            f"representing the client (buyer/licensee). Rewrite clauses to be more favourable to the client."
        )
        prompt = (
            f"Rewrite this contract clause to better protect the client's interests. "
            f"Keep the same structure but improve the legal language:\n\n{clause['text']}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception:
        return f"[Redline for {clause.get('type', 'clause')} — Gemini API unavailable]"


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
    return builder.compile(checkpointer=checkpointer, interrupt_before=["human_checkpoint"])


review_graph = build_review_graph()
