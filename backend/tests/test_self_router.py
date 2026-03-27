"""Tests for tools.self_router — 5-route classifier + multi-hop regex."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.self_router import (
    RouteResult,
    route_query,
    _score,
    _has_multi_hop_signal,
    get_retrieval_strategy,
    _DD_SIGNALS,
    _CONTRACT_SIGNALS,
    _GRAPH_SIGNALS,
    _DIRECT_SIGNALS,
)


# ── RouteResult ──────────────────────────────────────────────────────────────


class TestRouteResult:
    def test_to_dict(self):
        r = RouteResult("graph_rag", "high", 0.85, "test reason")
        d = r.to_dict()
        assert d == {
            "route": "graph_rag",
            "complexity": "high",
            "confidence": 0.85,
            "reason": "test reason",
        }

    def test_slots(self):
        r = RouteResult("vector_rag", "low", 0.5, "fallback")
        assert r.route == "vector_rag"
        assert r.complexity == "low"
        assert r.confidence == 0.5
        assert r.reason == "fallback"


# ── _score helper ────────────────────────────────────────────────────────────


class TestScore:
    def test_no_match(self):
        assert _score("hello world", _DD_SIGNALS) == 0

    def test_single_match(self):
        assert _score("run a due diligence check", _DD_SIGNALS) >= 1

    def test_multiple_matches(self):
        score = _score("due diligence on the target company for m&a", _DD_SIGNALS)
        assert score >= 3

    def test_case_insensitive_input(self):
        assert _score("review this contract", _CONTRACT_SIGNALS) >= 1

    def test_jp_signals(self):
        assert _score("この契約書をレビューしてください", _CONTRACT_SIGNALS) >= 2


# ── _has_multi_hop_signal ────────────────────────────────────────────────────


class TestMultiHopSignal:
    def test_en_relationship_between(self):
        assert _has_multi_hop_signal("What is the relationship between DGCL and SEC Act?")

    def test_en_how_does_interact(self):
        assert _has_multi_hop_signal("How does Article 330 interact with fiduciary duty?")

    def test_en_analogous_to(self):
        assert _has_multi_hop_signal("Is JP corporate governance analogous to US fiduciary duty?")

    def test_en_cross_jurisdiction(self):
        assert _has_multi_hop_signal("cross-jurisdictional comparison of disclosure rules")

    def test_jp_multi_hop(self):
        assert _has_multi_hop_signal("条文間の関係を教えてください")

    def test_jp_amendment(self):
        assert _has_multi_hop_signal("改正の前後で何が変わりましたか")

    def test_no_signal(self):
        assert not _has_multi_hop_signal("What is the Companies Act?")

    def test_empty(self):
        assert not _has_multi_hop_signal("")


# ── route_query ──────────────────────────────────────────────────────────────


class TestRouteQuery:
    def test_dd_agent_route(self):
        r = route_query("Run a due diligence investigation on the target company")
        assert r.route == "dd_agent"
        assert r.complexity == "high"

    def test_dd_agent_jp(self):
        r = route_query("対象会社のデューデリジェンスを実施してください")
        assert r.route == "dd_agent"

    def test_contract_agent_route(self):
        r = route_query("Please review this NDA contract and redline the indemnification clause")
        assert r.route == "contract_agent"
        assert r.complexity == "high"

    def test_contract_agent_jp(self):
        r = route_query("この契約書の条項をレビューしてください")
        assert r.route == "contract_agent"

    def test_graph_rag_route(self):
        r = route_query("What is the relationship between Article 330 and fiduciary duty?")
        assert r.route == "graph_rag"
        assert r.complexity == "high"

    def test_graph_rag_via_multi_hop(self):
        r = route_query("How does Section 10b interact with Rule 10b-5?")
        assert r.route == "graph_rag"

    def test_direct_answer_route(self):
        r = route_query("What is DGCL?")
        assert r.route == "direct_answer"
        assert r.complexity == "low"

    def test_direct_answer_jp(self):
        r = route_query("会社法とは")
        assert r.route == "direct_answer"

    def test_vector_rag_fallback(self):
        r = route_query("Explain the corporate governance requirements under Japanese law")
        assert r.route == "vector_rag"

    def test_confidence_capped(self):
        r = route_query("due diligence m&a merger acquisition target company investigate compliance check")
        assert r.confidence <= 0.95

    def test_long_query_high_complexity(self):
        long_query = "a " * 70  # >120 chars
        r = route_query(long_query)
        if r.route == "vector_rag":
            assert r.complexity == "high"

    def test_dd_single_signal_wins_when_no_others(self):
        r = route_query("run a compliance check on this entity")
        assert r.route == "dd_agent"


# ── get_retrieval_strategy ───────────────────────────────────────────────────


class TestRetrievalStrategy:
    def test_dd_agent_uses_both(self):
        s = get_retrieval_strategy("dd_agent")
        assert s["use_graph"] is True
        assert s["use_vector"] is True
        assert s["graph_hops"] == 2

    def test_contract_agent_vector_only(self):
        s = get_retrieval_strategy("contract_agent")
        assert s["use_graph"] is False
        assert s["use_vector"] is True

    def test_graph_rag_graph_only(self):
        s = get_retrieval_strategy("graph_rag")
        assert s["use_graph"] is True
        assert s["use_vector"] is False

    def test_vector_rag(self):
        s = get_retrieval_strategy("vector_rag")
        assert s["use_graph"] is False
        assert s["use_vector"] is True

    def test_direct_answer_no_retrieval(self):
        s = get_retrieval_strategy("direct_answer")
        assert s["use_graph"] is False
        assert s["use_vector"] is False
        assert s["graph_hops"] == 0

    def test_all_routes_covered(self):
        for route in ("dd_agent", "contract_agent", "graph_rag", "vector_rag", "direct_answer"):
            s = get_retrieval_strategy(route)
            assert isinstance(s, dict)
