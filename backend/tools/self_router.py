"""Self-Route router — classify a legal query into one of five retrieval routes.

Routes (RDD §8):
  dd_agent       — Due diligence request (M&A, corporate investigation)
  contract_agent — Contract review / redline request
  graph_rag      — Multi-hop graph traversal needed (cross-statute reasoning)
  vector_rag     — Semantic similarity search (chunk retrieval)
  direct_answer  — Simple definitional Q&A; no retrieval needed

Complexity estimate drives Qwen3 Swallow thinking mode:
  high   → /think   (dd_agent, contract_agent, graph_rag with long query)
  low    → /no_think (direct_answer, short vector_rag)

RDD §8.3 regex-based multi-hop signals are applied on top of keyword scoring
to promote vector_rag queries to graph_rag when multi-hop reasoning is needed.
"""

import re
from typing import Literal

Route = Literal["dd_agent", "contract_agent", "graph_rag", "vector_rag", "direct_answer"]
Complexity = Literal["high", "low"]


# ─── Signal keyword lists ─────────────────────────────────────────────────────

_DD_SIGNALS = [
    # EN
    "due diligence", "dd report", "m&a", "merger", "acquisition", "target company",
    "corporate investigation", "risk report", "transaction risk", "deal risk",
    "investigate", "investigate the target", "compliance check",
    # JP
    "デューデリジェンス", "Ｍ＆Ａ", "合併", "買収", "対象会社", "リスク調査",
    "コンプライアンス調査", "法務調査",
]

_CONTRACT_SIGNALS = [
    # EN
    "review this contract", "redline", "clause", "agreement", "NDA",
    "non-disclosure", "indemnification", "limitation of liability", "termination clause",
    "IP ownership", "governing law", "review the contract", "draft agreement",
    "contract analysis", "contract review",
    # JP
    "契約書", "レビュー", "条項", "機密保持", "損害賠償", "秘密保持契約",
    "解除条項", "準拠法", "契約のレビュー",
]

_GRAPH_SIGNALS = [
    # EN
    "relationship between", "how does", "compare", "analogous", "cross-reference",
    "cite", "referenced by", "governed by", "conflict between", "amend",
    "supersede", "interact", "article and", "provision of",
    # JP
    "関係", "比較", "類似", "相互参照", "引用", "準拠", "改正", "条文間",
    "条と", "条の関係",
]

_DIRECT_SIGNALS = [
    # EN
    "what is", "define", "definition of", "meaning of", "explain briefly",
    "what does", "who is", "when was",
    # JP
    "とは", "の定義", "の意味", "を教えて", "説明して",
]

# ─── Multi-hop regex signals (RDD §8.3) ──────────────────────────────────────
# These patterns indicate multi-step reasoning is required → graph_rag / high complexity.

_MULTI_HOP_PATTERNS: list[re.Pattern] = [
    # JP patterns
    re.compile(r"なぜ.{0,20}判断"),           # Why was X decided?
    re.compile(r"どのような.{0,20}影響"),      # What impact does X have?
    re.compile(r".{0,20}との関係"),            # Relationship between X and Y
    re.compile(r"改正.{0,10}前後"),            # Before/after amendment
    re.compile(r".{0,20}場合.{0,10}どうなる"), # What happens when X?
    re.compile(r".{0,20}要件.{0,10}すべて"),   # All requirements of X
    re.compile(r"条文間"),                     # Between provisions
    re.compile(r"根拠.{0,20}条文"),            # Basis provision
    re.compile(r"判例.{0,10}法理"),            # Case law doctrine
    re.compile(r"類推.{0,10}適用"),            # Analogical application
    # EN patterns
    re.compile(r"relationship between", re.I),
    re.compile(r"how does.{0,30}interact", re.I),
    re.compile(r"before\s+and\s+after\s+amend", re.I),
    re.compile(r"all\s+element[s]?\s+of", re.I),
    re.compile(r"analogous\s+to", re.I),
    re.compile(r"conflict\s+between", re.I),
    re.compile(r"chain\s+of\s+liability", re.I),
    re.compile(r"cross[\s-]jurisdict", re.I),
]


# ─── Router ───────────────────────────────────────────────────────────────────

class RouteResult:
    __slots__ = ("route", "complexity", "confidence", "reason")

    def __init__(self, route: Route, complexity: Complexity, confidence: float, reason: str):
        self.route = route
        self.complexity = complexity
        self.confidence = confidence
        self.reason = reason

    def to_dict(self) -> dict:
        return {
            "route": self.route,
            "complexity": self.complexity,
            "confidence": self.confidence,
            "reason": self.reason,
        }


def route_query(query: str, jurisdiction: str = "JP") -> RouteResult:
    """Classify query into a retrieval route and complexity level.

    Algorithm:
      1. Score each route by keyword hits (case-insensitive).
      2. Direct-answer wins only when no other signals fire.
      3. Complexity = high for agents and multi-hop graph; low otherwise.
    """
    lower = query.lower()
    length = len(query)

    dd_score = _score(lower, _DD_SIGNALS)
    contract_score = _score(lower, _CONTRACT_SIGNALS)
    graph_score = _score(lower, _GRAPH_SIGNALS)
    direct_score = _score(lower, _DIRECT_SIGNALS)

    # ── Agent routes win if their score is high ───────────────────────────────
    if dd_score >= 2 or (dd_score == 1 and contract_score == 0 and graph_score == 0):
        return RouteResult("dd_agent", "high", min(0.6 + dd_score * 0.1, 0.95),
                           f"DD signals: {dd_score}")

    if contract_score >= 1:
        return RouteResult("contract_agent", "high", min(0.65 + contract_score * 0.1, 0.95),
                           f"Contract signals: {contract_score}")

    # ── Multi-hop regex: promote to graph_rag even without keyword signals ────
    multi_hop = _has_multi_hop_signal(query)

    # ── Graph RAG for relational / comparative queries ────────────────────────
    if graph_score >= 1 or multi_hop:
        complexity: Complexity = "high"
        reason = f"Graph signals: {graph_score}" + (" + multi-hop regex" if multi_hop else "")
        return RouteResult("graph_rag", complexity,
                           min(0.55 + graph_score * 0.1 + (0.15 if multi_hop else 0), 0.95),
                           reason)

    # ── Direct answer for simple definitional questions ───────────────────────
    if direct_score >= 1 and length < 80:
        return RouteResult("direct_answer", "low",
                           min(0.50 + direct_score * 0.1, 0.85),
                           f"Direct signals: {direct_score}, short query")

    # ── Default: vector RAG ───────────────────────────────────────────────────
    complexity = "high" if length > 120 else "low"
    return RouteResult("vector_rag", complexity, 0.5, "No strong signals — semantic search")


def _score(lower: str, signals: list[str]) -> int:
    return sum(1 for s in signals if s in lower)


def _has_multi_hop_signal(query: str) -> bool:
    """Return True if any RDD §8.3 multi-hop regex pattern matches the query."""
    return any(p.search(query) for p in _MULTI_HOP_PATTERNS)


# ─── Route log ───────────────────────────────────────────────────────────────

def log_route(route_result: RouteResult, query: str, latency_ms: int) -> None:
    """Persist routing decision to Supabase route_logs table (non-fatal)."""
    try:
        import os
        from supabase import create_client
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            return
        client = create_client(url, key)
        client.table("route_logs").insert({
            "query":      query[:500],
            "route_used": route_result.route,
            "confidence": route_result.confidence,
            "latency_ms": latency_ms,
        }).execute()
    except Exception as e:
        print(f"[self_router] route log error (non-fatal): {e}")


# ─── Retrieval strategy per route ────────────────────────────────────────────

def get_retrieval_strategy(route: Route) -> dict:
    """Return which retrievers to call for each route."""
    strategies: dict[Route, dict] = {
        "dd_agent":       {"use_graph": True,  "use_vector": True,  "graph_hops": 2},
        "contract_agent": {"use_graph": False, "use_vector": True,  "graph_hops": 0},
        "graph_rag":      {"use_graph": True,  "use_vector": False, "graph_hops": 2},
        "vector_rag":     {"use_graph": False, "use_vector": True,  "graph_hops": 0},
        "direct_answer":  {"use_graph": False, "use_vector": False, "graph_hops": 0},
    }
    return strategies[route]
