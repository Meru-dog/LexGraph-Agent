"""LangGraph state schemas for DD Agent and Contract Review Agent."""

from typing import TypedDict, List, Dict, Optional
from langchain_core.messages import BaseMessage


# ─── DD Agent ─────────────────────────────────────────────────────────────────


class Finding(TypedDict):
    status: str          # "critical" | "high" | "warn" | "ok"
    text: str
    section: str
    citations: List[str]


class RiskMatrix(TypedDict):
    critical: List[Finding]
    high: List[Finding]
    medium: List[Finding]
    low: List[Finding]


class DDReport(TypedDict):
    target: str
    transaction: str
    date: str
    jurisdiction: str
    summary: dict
    sections: List[dict]


class DDState(TypedDict):
    # Input
    transaction_type: str
    jurisdiction: str           # "JP" | "US" | "both"
    documents: List[dict]
    prompt: str
    model_name: str             # "gemini" | "llama" | "fine_tuned"

    # Planning
    dd_checklist: List[dict]

    # Sub-investigation outputs (populated in parallel)
    corporate_findings: List[Finding]
    contract_findings: List[Finding]
    regulatory_findings: List[Finding]
    financial_findings: List[Finding]
    legal_findings: List[Finding]
    business_findings: List[Finding]

    # Synthesis
    risk_matrix: RiskMatrix

    # Human loop
    attorney_notes: str
    approved: bool
    reinvestigation_targets: List[str]

    # Output
    dd_report: Optional[DDReport]
    messages: List[BaseMessage]


# ─── Contract Review Agent ─────────────────────────────────────────────────────


class Clause(TypedDict):
    id: str
    type: str           # "payment" | "ip" | "termination" | "liability" | ...
    text: str
    position: int       # character offset in original


class ClauseReview(TypedDict):
    clause_id: str
    risk_level: str     # "critical" | "high" | "medium" | "low"
    issues: List[str]
    redline_suggestion: str
    redline_reason: str  # Brief explanation of why this clause was rewritten
    text_snippet: str    # First ~100 chars of original clause text (for diff matching)
    applicable_statutes: List[str]
    citations: List[str]


class Inconsistency(TypedDict):
    clause_a_id: str
    clause_b_id: str
    description: str


class ComplianceFlag(TypedDict):
    clause_id: str
    statute: str
    issue: str
    severity: str


class ContractReviewState(TypedDict):
    # Input
    raw_contract: str
    jurisdiction: str
    contract_type: str
    client_position: str

    # Parsing
    clauses: List[Clause]

    # Per-clause review
    clause_reviews: List[ClauseReview]

    # Cross-reference
    inconsistencies: List[Inconsistency]

    # Statute compliance
    compliance_flags: List[ComplianceFlag]

    # Human loop
    attorney_redlines: Dict[str, str]   # clause_id → attorney text
    approved_clauses: List[str]

    # Output
    redlined_contract: str
    review_report: dict
    messages: List[BaseMessage]
