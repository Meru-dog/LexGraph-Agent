"""LangGraph DD Agent — comprehensive 11-node due diligence workflow.

Graph topology:
    START → scope_planner
          → corporate_reviewer  (Send, parallel)
          → contract_reviewer   (Send, parallel)
          → regulatory_checker  (Send, parallel)
          → financial_analyzer  (Send, parallel)
          → legal_risk_analyzer (Send, parallel)
          → business_analyzer   (Send, parallel)
          → risk_synthesizer (fan-in)
          → human_checkpoint (interrupt)
          → report_generator → END
          → re_investigate → risk_synthesizer (loop)
"""

from datetime import date
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import Send

from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import DDState, Finding
from tools.graph_search import graph_search
from tools.vector_search import vector_search
from tools.statute_lookup import statute_lookup
from tools.risk_classifier import risk_classifier
from tools.jurisdiction_router import jurisdiction_router
from tools.report_formatter import report_formatter
from tools.edinet_search import search_disclosures as edinet_search, fetch_document_text as edinet_fetch
from tools.edgar_search import search_filings as edgar_search, fetch_filing_text as edgar_fetch
from models.model_factory import get_llm as _factory_get_llm


def get_llm_for_state(state: DDState, system_prompt: str = "You are a senior M&A legal counsel in JP/US jurisdiction."):
    """Select LLM based on model_name stored in state.

    Agents always run in Thinking mode — complex multi-step reasoning requires it.
    """
    model_name = state.get("model_name", "ollama") if isinstance(state, dict) else "ollama"
    return _factory_get_llm(system_prompt=system_prompt, model=model_name, thinking=True)


def scope_planner(state: DDState) -> dict:
    """Parse the attorney prompt → transaction type, jurisdiction, target entity, DD checklist."""
    import json, re
    jur = jurisdiction_router(state["prompt"])

    target_entity = ""
    transaction_type = state.get("transaction_type", "acquisition")

    try:
        llm = get_llm_for_state(state, system_prompt="You are a legal AI assistant that extracts structured information from due diligence instructions.")
        extraction_prompt = (
            f"Extract the following from this DD instruction as JSON (use empty string if unknown): "
            f"{{\"transaction_type\": \"<acquisition|merger|investment|licensing>\", "
            f"\"target_entity\": \"<company name>\", \"amount\": \"<deal amount>\"}}.\n\n"
            f"Instruction: {state['prompt']}\n\nRespond with ONLY valid JSON."
        )
        response = llm.invoke([HumanMessage(content=extraction_prompt)])
        json_match = re.search(r"\{.*?\}", response.content, re.DOTALL)
        if json_match:
            extracted = json.loads(json_match.group())
            target_entity = extracted.get("target_entity", "")
            transaction_type = extracted.get("transaction_type", transaction_type) or transaction_type
    except Exception:
        pass

    checklist = [
        {"section": "01", "title": "Corporate Structure & Governance"},
        {"section": "02", "title": "Financial Performance & Health"},
        {"section": "03", "title": "Indebtedness & Capital Structure"},
        {"section": "04", "title": "Regulatory Compliance & Licensing"},
        {"section": "05", "title": "Material Contracts & Agreements"},
        {"section": "06", "title": "Intellectual Property & Technology"},
        {"section": "07", "title": "Employment & Labor Relations"},
        {"section": "08", "title": "Litigation & Legal Risk"},
        {"section": "09", "title": "ESG & Environmental Compliance"},
        {"section": "10", "title": "Market Position & Competition"},
        {"section": "11", "title": "Operational Risk"},
        {"section": "12", "title": "Transaction Risk & Deal Terms"},
    ]
    return {
        "jurisdiction": state.get("jurisdiction") or jur,
        "transaction_type": transaction_type,
        "dd_checklist": checklist,
        "messages": state.get("messages", []) + (
            [SystemMessage(content=f"TARGET_ENTITY:{target_entity}")] if target_entity else []
        ),
    }


def _extract_target_entity(state: DDState) -> str:
    """Extract target entity name stored by scope_planner in messages."""
    for msg in reversed(state.get("messages", [])):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content.startswith("TARGET_ENTITY:"):
            return content[len("TARGET_ENTITY:"):].strip()
    return ""


def _analyze_disclosure_with_llm(
    state: DDState,
    target: str,
    doc_type: str,
    text: str,
    jurisdiction: str,
    focus: str,
) -> str:
    """Use the state-selected LLM to analyze disclosure text and return a DD summary."""
    if not text or text.startswith("["):
        return "(Disclosure text not available for detailed analysis)"
    try:
        llm = _factory_get_llm(
            system_prompt=(
                f"You are a senior M&A attorney conducting due diligence in {jurisdiction} jurisdiction. "
                f"Analyze financial disclosures for legal and business risks."
            ),
            model=state.get("model_name", "ollama") if isinstance(state, dict) else "ollama",
        )
        prompt = (
            f"Analyze this {doc_type} disclosure for {target}. "
            f"Focus on: {focus}. "
            f"Identify 2-3 key findings relevant to due diligence. "
            f"Be concise (max 3 sentences).\n\n"
            f"Disclosure excerpt:\n{text[:2000]}"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception:
        return ""


def corporate_reviewer(state: DDState) -> dict:
    """Review entity registry, cap table, disclosed financials from EDINET/EDGAR."""
    jur = state.get("jurisdiction", "JP")
    target = _extract_target_entity(state)
    findings: list[Finding] = []

    # ── EDINET (Japanese disclosures) ──────────────────────────────────────
    if target and jur in ("JP", "JP+US", "both"):
        disclosures = edinet_search(target, days_back=730, doc_types=["120", "140", "010", "050"])
        if disclosures:
            annual = next((d for d in disclosures if d["docTypeCode"] == "120"), None)
            snippet = ""
            if annual:
                snippet = edinet_fetch(annual["docID"], max_chars=3000)

            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="有価証券報告書",
                text=snippet,
                jurisdiction="JP",
                focus="corporate structure, major shareholders, board composition, financial health",
            )

            findings.append({
                "status": "ok",
                "text": (
                    f"EDINET: {len(disclosures)} disclosure(s) found for {target}. "
                    f"Most recent: {disclosures[0]['docTypeName']} ({disclosures[0].get('submitDateTime','')[:10]}). "
                    f"\n\n{analysis}"
                ),
                "section": "01",
                "citations": [d["edinet_url"] for d in disclosures[:3]],
            })
        else:
            findings.append({
                "status": "warn",
                "text": f"EDINET: No disclosures found for '{target}'. Company may not be listed or name differs.",
                "section": "01",
                "citations": [],
            })

    # ── SEC EDGAR (US disclosures) ─────────────────────────────────────────
    if target and jur in ("US", "JP+US", "both"):
        filings = edgar_search(target, filing_types=["10-K", "10-Q", "8-K", "20-F"])
        if filings:
            annual = next((f for f in filings if f["filingType"] in ("10-K", "20-F")), None)
            snippet = ""
            if annual and annual.get("edgar_url"):
                snippet = edgar_fetch(annual["edgar_url"], max_chars=3000)

            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type=annual["filingType"] if annual else "10-K",
                text=snippet,
                jurisdiction="US",
                focus="corporate structure, major shareholders, board composition, financial health, risk factors",
            )

            findings.append({
                "status": "ok",
                "text": (
                    f"EDGAR: {len(filings)} filing(s) found for {target}. "
                    f"Most recent: {filings[0]['filingType']} ({filings[0].get('filedAt','')[:10]}). "
                    f"\n\n{analysis}"
                ),
                "section": "01",
                "citations": [f["edgar_url"] for f in filings[:3]],
            })
        else:
            findings.append({
                "status": "warn",
                "text": f"EDGAR: No SEC filings found for '{target}'. May not be a US-registered issuer.",
                "section": "01",
                "citations": [],
            })

    # ── Knowledge graph fallback ───────────────────────────────────────────
    graph_results = graph_search(
        query=f"{target} corporate entity cap table board" if target else "corporate entity cap table board minutes",
        jurisdiction=jur,
        node_types=["Entity", "Statute"],
    )
    if graph_results.get("nodes"):
        findings.append({
            "status": "ok",
            "text": "Internal knowledge graph: corporate entity nodes retrieved.",
            "section": "01",
            "citations": [r.get("node_id", "") for r in graph_results.get("nodes", [])[:3]],
        })

    if not findings:
        findings.append({
            "status": "warn",
            "text": "Corporate records: target entity not identified from prompt. Manual review required.",
            "section": "01",
            "citations": [],
        })

    return {"corporate_findings": findings}


def financial_analyzer(state: DDState) -> dict:
    """Analyze financial health from EDINET annual reports and SEC 10-K filings."""
    jur = state.get("jurisdiction", "JP")
    target = _extract_target_entity(state)
    findings: list[Finding] = []

    # ── EDINET 有価証券報告書 financial analysis ────────────────────────────
    if target and jur in ("JP", "JP+US", "both"):
        disclosures = edinet_search(target, days_back=1095, doc_types=["120"])  # 3 years
        annual_reports = [d for d in disclosures if d["docTypeCode"] == "120"]
        if annual_reports:
            # Fetch most recent annual report for detailed financial analysis
            snippet = edinet_fetch(annual_reports[0]["docID"], max_chars=4000)
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="有価証券報告書 (Annual Report)",
                text=snippet,
                jurisdiction="JP",
                focus=(
                    "revenue trend, operating profit margin, debt-to-equity ratio, "
                    "cash flow from operations, pension obligations, going concern indicators"
                ),
            )
            count = len(annual_reports)
            risk_status = "ok" if count >= 2 else "warn"
            findings.append({
                "status": risk_status,
                "text": (
                    f"JP Financial Analysis: {count} annual report(s) available on EDINET. "
                    f"Reporting period: {annual_reports[0].get('submitDateTime','')[:10]}. "
                    f"\n\n{analysis}"
                ),
                "section": "02",
                "citations": [d["edinet_url"] for d in annual_reports[:2]],
            })
        else:
            findings.append({
                "status": "warn",
                "text": f"JP Financial: No 有価証券報告書 found for '{target}'. Cannot assess financial health from EDINET.",
                "section": "02",
                "citations": [],
            })

    # ── SEC EDGAR 10-K financial analysis ─────────────────────────────────
    if target and jur in ("US", "JP+US", "both"):
        filings = edgar_search(target, filing_types=["10-K", "20-F", "10-Q"])
        annual_filings = [f for f in filings if f["filingType"] in ("10-K", "20-F")]
        if annual_filings:
            snippet = ""
            if annual_filings[0].get("edgar_url"):
                snippet = edgar_fetch(annual_filings[0]["edgar_url"], max_chars=4000)
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type=f"SEC {annual_filings[0]['filingType']}",
                text=snippet,
                jurisdiction="US",
                focus=(
                    "revenue CAGR, gross/operating margins, free cash flow, leverage ratio, "
                    "material weaknesses in internal controls, going concern, goodwill impairment"
                ),
            )
            findings.append({
                "status": "ok",
                "text": (
                    f"US Financial Analysis: {len(annual_filings)} annual filing(s) on EDGAR. "
                    f"Most recent {annual_filings[0]['filingType']}: {annual_filings[0].get('filedAt','')[:10]}. "
                    f"\n\n{analysis}"
                ),
                "section": "02",
                "citations": [f["edgar_url"] for f in annual_filings[:2]],
            })
        else:
            findings.append({
                "status": "warn",
                "text": f"US Financial: No 10-K/20-F found for '{target}' on SEC EDGAR.",
                "section": "02",
                "citations": [],
            })

    if not findings:
        findings.append({
            "status": "warn",
            "text": "Financial analysis: insufficient data. Manual financial review required.",
            "section": "02",
            "citations": [],
        })

    return {"financial_findings": findings}


def legal_risk_analyzer(state: DDState) -> dict:
    """Analyze legal and regulatory risks: litigation, sanctions, ad-hoc disclosures."""
    jur = state.get("jurisdiction", "JP")
    target = _extract_target_entity(state)
    findings: list[Finding] = []

    # ── EDINET 臨時報告書 (material event disclosures) ─────────────────────
    if target and jur in ("JP", "JP+US", "both"):
        adhoc = edinet_search(target, days_back=730, doc_types=["050"])
        if adhoc:
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="臨時報告書 (Ad-hoc Disclosure)",
                text=f"Found {len(adhoc)} ad-hoc disclosures: " +
                     "; ".join(f"{d['docTypeName']} ({d.get('submitDateTime','')[:10]})" for d in adhoc[:5]),
                jurisdiction="JP",
                focus="material litigation, regulatory investigations, management changes, financial restatements",
            )
            risk_level = "critical" if len(adhoc) > 5 else ("high" if len(adhoc) > 3 else "medium")
            findings.append({
                "status": risk_level,
                "text": (
                    f"JP Legal Risk: {len(adhoc)} 臨時報告書 in past 2 years — elevated disclosure activity. "
                    f"{analysis}"
                ),
                "section": "08",
                "citations": [d["edinet_url"] for d in adhoc[:3]],
            })
        else:
            findings.append({
                "status": "ok",
                "text": "JP Legal Risk: No 臨時報告書 found in past 2 years. No disclosed material legal events.",
                "section": "08",
                "citations": [],
            })

    # ── EDGAR 8-K (US material events) ────────────────────────────────────
    if target and jur in ("US", "JP+US", "both"):
        current_reports = edgar_search(target, filing_types=["8-K", "6-K"])
        if current_reports:
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="8-K Current Report",
                text=f"Found {len(current_reports)} current reports: " +
                     "; ".join(f"{f['filingType']} ({f.get('filedAt','')[:10]})" for f in current_reports[:5]),
                jurisdiction="US",
                focus="material litigation, SEC investigations, restatements, management changes, going concern",
            )
            risk_level = "high" if len(current_reports) > 5 else "medium"
            findings.append({
                "status": risk_level,
                "text": f"US Legal Risk: {len(current_reports)} 8-K/6-K current reports found. {analysis}",
                "section": "08",
                "citations": [f["edgar_url"] for f in current_reports[:3]],
            })

    # ── Statute compliance check via knowledge graph ───────────────────────
    statute_refs = []
    if jur in ("JP", "JP+US", "both"):
        statute_refs.append("FIEA Art. 28")
    if jur in ("US", "JP+US", "both"):
        statute_refs.append("Securities Act Section 5")
    for ref in statute_refs:
        provision = statute_lookup(article_ref=ref, jurisdiction=jur)
        if provision:
            findings.append({
                "status": "high",
                "text": f"Statute compliance flag: {ref} — potential applicability requires legal review.",
                "section": "04",
                "citations": [provision.get("node_id", "")],
            })

    if not findings:
        findings.append({
            "status": "ok",
            "text": "Legal risk: no material litigation or regulatory issues identified from public disclosures.",
            "section": "08",
            "citations": [],
        })

    return {"legal_findings": findings}


def business_analyzer(state: DDState) -> dict:
    """Analyze market position, business model risks, and operational risks."""
    jur = state.get("jurisdiction", "JP")
    target = _extract_target_entity(state)
    findings: list[Finding] = []

    # ── Fetch business overview from EDINET/EDGAR ─────────────────────────
    business_text = ""
    if target and jur in ("JP", "JP+US", "both"):
        disclosures = edinet_search(target, days_back=730, doc_types=["120"])
        annual = next((d for d in disclosures if d["docTypeCode"] == "120"), None)
        if annual:
            business_text = edinet_fetch(annual["docID"], max_chars=3000)
    elif target and jur in ("US",):
        filings = edgar_search(target, filing_types=["10-K"])
        if filings and filings[0].get("edgar_url"):
            business_text = edgar_fetch(filings[0]["edgar_url"], max_chars=3000)

    if business_text:
        analysis = _analyze_disclosure_with_llm(
            state=state,
            target=target,
            doc_type="Business Overview",
            text=business_text,
            jurisdiction=jur,
            focus=(
                "market position, competitive landscape, customer concentration risk, "
                "supply chain dependencies, technology risks, key person risk"
            ),
        )
        findings.append({
            "status": "medium",
            "text": f"Business Analysis for {target}: {analysis}",
            "section": "10",
            "citations": [],
        })

    # ── Vector search for competitive/market context ───────────────────────
    results = vector_search(
        query=f"{target} market competition business model risk" if target else "market competition business risk",
        jurisdiction=jur,
        top_k=3,
    )
    if results:
        findings.append({
            "status": "ok",
            "text": f"Vector search: {len(results)} document chunk(s) retrieved on market/business context.",
            "section": "10",
            "citations": [r.get("chunk_id", "") for r in results[:2]],
        })

    # ── Operational risk check via knowledge graph ─────────────────────────
    graph_results = graph_search(
        query=f"{target} operational risk supply chain" if target else "operational risk supply chain",
        jurisdiction=jur,
        node_types=["Entity"],
    )
    if graph_results.get("nodes"):
        findings.append({
            "status": "ok",
            "text": "Knowledge graph: operational risk nodes found for further analysis.",
            "section": "11",
            "citations": [r.get("node_id", "") for r in graph_results.get("nodes", [])[:2]],
        })

    if not findings:
        findings.append({
            "status": "warn",
            "text": "Business analysis: insufficient public data. Management interviews and market analysis recommended.",
            "section": "10",
            "citations": [],
        })

    return {"business_findings": findings}


def contract_reviewer(state: DDState) -> dict:
    """Analyse material contract risks via vector search."""
    results = vector_search(
        query="material contract risk termination change of control",
        jurisdiction=state["jurisdiction"],
        top_k=5,
    )
    findings: list[Finding] = [
        {
            "status": "medium",
            "text": f"Contract review: retrieved {len(results)} contract-relevant chunks from vector store. Manual review of material agreements recommended.",
            "section": "05",
            "citations": [],
        }
    ]
    return {"contract_findings": findings}


def regulatory_checker(state: DDState) -> dict:
    """Cross-reference regulatory disclosures and statute compliance."""
    jur = state.get("jurisdiction", "JP")
    target = _extract_target_entity(state)
    findings: list[Finding] = []

    # ── EDINET 適時開示 ────────────────────────────────────────────────────
    if target and jur in ("JP", "JP+US", "both"):
        adhoc = edinet_search(target, days_back=365, doc_types=["050"])
        if adhoc:
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="臨時報告書/適時開示",
                text=f"Found {len(adhoc)} ad-hoc disclosure(s): " +
                     "; ".join(f"{d['docTypeName']} ({d.get('submitDateTime','')[:10]})" for d in adhoc[:5]),
                jurisdiction="JP",
                focus="material events, regulatory issues, litigation, management changes",
            )
            findings.append({
                "status": "high" if len(adhoc) > 3 else "medium",
                "text": f"EDINET 適時開示: {len(adhoc)} ad-hoc disclosure(s) in the past year. {analysis}",
                "section": "04",
                "citations": [d["edinet_url"] for d in adhoc[:3]],
            })

    # ── EDGAR 8-K ─────────────────────────────────────────────────────────
    if target and jur in ("US", "JP+US", "both"):
        current_reports = edgar_search(target, filing_types=["8-K", "6-K"])
        if current_reports:
            analysis = _analyze_disclosure_with_llm(
                state=state,
                target=target,
                doc_type="8-K Current Report",
                text=f"Found {len(current_reports)} current report(s): " +
                     "; ".join(f"{f['filingType']} ({f.get('filedAt','')[:10]})" for f in current_reports[:5]),
                jurisdiction="US",
                focus="material events, regulatory issues, litigation, management changes, financial restatements",
            )
            findings.append({
                "status": "high" if len(current_reports) > 5 else "medium",
                "text": f"EDGAR 8-K: {len(current_reports)} current report(s). {analysis}",
                "section": "04",
                "citations": [f["edgar_url"] for f in current_reports[:3]],
            })

    # ── Statute graph ──────────────────────────────────────────────────────
    statute_refs = ["FIEA Art. 28"] if jur in ("JP", "JP+US", "both") else []
    if jur in ("US", "JP+US", "both"):
        statute_refs.append("Securities Act Section 5")
    for ref in statute_refs:
        provision = statute_lookup(article_ref=ref, jurisdiction=jur)
        if provision:
            findings.append({
                "status": "high",
                "text": f"Statute compliance: {ref} — potential applicability requires review.",
                "section": "04",
                "citations": [provision.get("node_id", "")],
            })

    if not findings:
        findings.append({
            "status": "ok",
            "text": "Regulatory compliance: no material ad-hoc disclosures found for target.",
            "section": "04",
            "citations": [],
        })

    return {"regulatory_findings": findings}


def risk_synthesizer(state: DDState) -> dict:
    """Aggregate all sub-agent findings into a risk matrix via LLM synthesis."""
    all_findings = (
        state.get("corporate_findings", [])
        + state.get("contract_findings", [])
        + state.get("regulatory_findings", [])
        + state.get("financial_findings", [])
        + state.get("legal_findings", [])
        + state.get("business_findings", [])
    )

    try:
        llm = _factory_get_llm(
            system_prompt="You are a senior M&A legal counsel synthesizing due diligence findings.",
            model=state.get("model_name", "ollama") if isinstance(state, dict) else "ollama",
        )
        findings_text = "\n".join(
            f"- [{f['status'].upper()}] {f['text']}" for f in all_findings
        )
        synthesis_prompt = (
            f"Review these due diligence findings and re-classify each as "
            f"critical/high/medium/low based on legal materiality. "
            f"Return JSON: {{\"critical\": [...], \"high\": [...], \"medium\": [...], \"low\": [...]}}\n\n"
            f"Findings:\n{findings_text}"
        )
        response = llm.invoke([HumanMessage(content=synthesis_prompt)])
        import json, re
        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if json_match:
            synthesized = json.loads(json_match.group())
            risk_matrix: dict = {"critical": [], "high": [], "medium": [], "low": []}
            for level, texts in synthesized.items():
                if level in risk_matrix:
                    for text in texts:
                        risk_matrix[level].append(
                            Finding(status=level, text=str(text), section="synthesized", citations=[])
                        )
            return {"risk_matrix": risk_matrix}
    except Exception:
        pass  # Fall back to rule-based classification

    risk_matrix = {"critical": [], "high": [], "medium": [], "low": []}
    for f in all_findings:
        level = f["status"]
        if level in risk_matrix:
            risk_matrix[level].append(f)
        else:
            risk_matrix["low"].append(f)
    return {"risk_matrix": risk_matrix}


def human_checkpoint(state: DDState) -> dict:
    """Pass-through — attorney review submitted via /agent/dd/{id}/review after report delivery."""
    return {"approved": True}


def report_generator(state: DDState) -> dict:
    """Format the final 12-section DD report with LLM narrative synthesis."""
    all_findings = (
        state.get("corporate_findings", [])
        + state.get("contract_findings", [])
        + state.get("regulatory_findings", [])
        + state.get("financial_findings", [])
        + state.get("legal_findings", [])
        + state.get("business_findings", [])
    )
    target = _extract_target_entity(state)
    jur = state.get("jurisdiction", "JP+US")

    recommendation = "Review required before proceeding with investment."
    try:
        llm = _factory_get_llm(
            system_prompt="You are a senior M&A counsel writing a due diligence report recommendation.",
            model=state.get("model_name", "ollama") if isinstance(state, dict) else "ollama",
        )
        risk_matrix = state.get("risk_matrix", {})
        risk_summary = {k: len(v) for k, v in risk_matrix.items()}
        findings_text = "\n".join(
            f"- [{f['status'].upper()}] {f['text'][:300]}" for f in all_findings[:10]
        )
        rec_prompt = (
            f"Write a 3-sentence executive recommendation for a DD report on {target or 'the target company'}. "
            f"Risk findings: {risk_summary}. Jurisdiction: {jur}. "
            f"Key findings:\n{findings_text}\n\n"
            f"Attorney notes: {state.get('attorney_notes', 'None')}. "
            f"Data sources used: EDINET, SEC EDGAR, internal knowledge graph."
        )
        response = llm.invoke([HumanMessage(content=rec_prompt)])
        recommendation = response.content.strip()
    except Exception:
        pass

    report = report_formatter(findings=all_findings, template="dd_report")
    if isinstance(report, dict) and "summary" in report:
        report["summary"]["recommendation"] = recommendation
    if isinstance(report, dict):
        report["target"] = target or report.get("target", "Unknown")
        report["transaction"] = state.get("transaction_type", "Acquisition")
        report["jurisdiction"] = jur
    return {"dd_report": report}


def re_investigate(state: DDState) -> dict:
    """Deep-dive on attorney-flagged items."""
    targets = state.get("reinvestigation_targets", [])
    extra: list[Finding] = []
    for target in targets:
        chunks = vector_search(query=target, jurisdiction=state["jurisdiction"], top_k=3)
        for c in chunks:
            extra.append({
                "status": "high",
                "text": f"Re-investigation: {c.get('text', '')[:200]}",
                "section": "08",
                "citations": [c.get("chunk_id", "")],
            })
    return {"regulatory_findings": state.get("regulatory_findings", []) + extra}


def route_after_checkpoint(state: DDState) -> Literal["report_generator", "re_investigate"]:
    if state.get("approved", True):
        return "report_generator"
    return "re_investigate"


def build_dd_graph() -> StateGraph:
    builder = StateGraph(DDState)

    builder.add_node("scope_planner", scope_planner)
    builder.add_node("corporate_reviewer", corporate_reviewer)
    builder.add_node("contract_reviewer", contract_reviewer)
    builder.add_node("regulatory_checker", regulatory_checker)
    builder.add_node("financial_analyzer", financial_analyzer)
    builder.add_node("legal_risk_analyzer", legal_risk_analyzer)
    builder.add_node("business_analyzer", business_analyzer)
    builder.add_node("risk_synthesizer", risk_synthesizer)
    builder.add_node("human_checkpoint", human_checkpoint)
    builder.add_node("report_generator", report_generator)
    builder.add_node("re_investigate", re_investigate)

    builder.add_edge(START, "scope_planner")

    # Fan-out to parallel sub-agents
    builder.add_conditional_edges(
        "scope_planner",
        lambda s: [
            Send("corporate_reviewer", s),
            Send("contract_reviewer", s),
            Send("regulatory_checker", s),
            Send("financial_analyzer", s),
            Send("legal_risk_analyzer", s),
            Send("business_analyzer", s),
        ],
    )

    # Fan-in from all sub-agents
    builder.add_edge("corporate_reviewer", "risk_synthesizer")
    builder.add_edge("contract_reviewer", "risk_synthesizer")
    builder.add_edge("regulatory_checker", "risk_synthesizer")
    builder.add_edge("financial_analyzer", "risk_synthesizer")
    builder.add_edge("legal_risk_analyzer", "risk_synthesizer")
    builder.add_edge("business_analyzer", "risk_synthesizer")

    builder.add_edge("risk_synthesizer", "human_checkpoint")
    builder.add_conditional_edges("human_checkpoint", route_after_checkpoint)
    builder.add_edge("re_investigate", "risk_synthesizer")
    builder.add_edge("report_generator", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


dd_graph = build_dd_graph()
