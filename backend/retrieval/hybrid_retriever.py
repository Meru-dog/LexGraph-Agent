"""HybridRetriever — 4-stage legal retrieval pipeline (RDD §9).

Stages:
  1. Vector search   — pgvector semantic similarity (multilingual-e5-large)
  2. Keyword search  — Neo4j FULLTEXT index on Statute/Case/Provision text
  3. Graph BFS       — 2-hop Neo4j traversal from fulltext anchor nodes
  4. CrossEncoder    — rerank merged candidates (cross-encoder/ms-marco-MiniLM-L-6-v2)

All stages filter status=ACTIVE so repealed law is never surfaced.
Stages 2–3 are skipped if Neo4j is not connected.
Stage 4 is skipped if sentence-transformers is not installed.
"""

from __future__ import annotations

import hashlib
from typing import List


# ─── Result type ─────────────────────────────────────────────────────────────

class RetrievalResult:
    """Single retrieved chunk/node with merged score."""

    __slots__ = ("id", "text", "source", "score", "metadata")

    def __init__(self, id: str, text: str, source: str, score: float, metadata: dict):
        self.id = id
        self.text = text
        self.source = source      # "vector" | "keyword" | "graph"
        self.score = score
        self.metadata = metadata  # jurisdiction, law_name, article_no, status, etc.

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "score": self.score,
            **self.metadata,
        }


# ─── HybridRetriever ─────────────────────────────────────────────────────────

class HybridRetriever:
    """Orchestrates the 4-stage retrieval pipeline."""

    def __init__(
        self,
        top_k_vector: int = 10,
        top_k_keyword: int = 10,
        top_k_graph: int = 20,
        top_k_final: int = 5,
        rerank: bool = True,
    ):
        self.top_k_vector = top_k_vector
        self.top_k_keyword = top_k_keyword
        self.top_k_graph = top_k_graph
        self.top_k_final = top_k_final
        self.rerank = rerank
        self._cross_encoder = None  # lazy-loaded

    def retrieve(
        self,
        query: str,
        jurisdiction: str,
        use_graph: bool = True,
        use_vector: bool = True,
    ) -> List[RetrievalResult]:
        """Run the full pipeline and return top_k_final reranked results."""
        candidates: dict[str, RetrievalResult] = {}

        if use_vector:
            for r in self._stage_vector(query, jurisdiction):
                candidates[r.id] = r

        if use_graph:
            for r in self._stage_keyword(query, jurisdiction):
                if r.id in candidates:
                    # Merge: boost score when found by both stages
                    candidates[r.id].score = max(candidates[r.id].score, r.score) + 0.1
                    candidates[r.id].source = "vector+keyword"
                else:
                    candidates[r.id] = r

            for r in self._stage_graph_bfs(query, jurisdiction):
                if r.id not in candidates:
                    candidates[r.id] = r

        if not candidates:
            return []

        merged = list(candidates.values())

        if self.rerank and len(merged) > 1:
            merged = self._stage_rerank(query, merged)
        else:
            merged.sort(key=lambda x: x.score, reverse=True)

        return merged[: self.top_k_final]

    # ── Stage 1: Vector search ────────────────────────────────────────────────

    def _stage_vector(self, query: str, jurisdiction: str) -> List[RetrievalResult]:
        try:
            from ingestion.embedder import search_chunks
            raw = search_chunks(query, jurisdiction, self.top_k_vector, status="ACTIVE")
            return [
                RetrievalResult(
                    id=c.get("chunk_id") or _stable_id(c.get("text", "")),
                    text=c.get("text", ""),
                    source="vector",
                    score=float(c.get("score", 0.5)),
                    metadata={
                        "jurisdiction": c.get("jurisdiction", ""),
                        "law_name":     c.get("law_name", ""),
                        "article_no":   c.get("article_no", ""),
                        "status":       c.get("status", "ACTIVE"),
                        "doc_id":       c.get("doc_id", ""),
                    },
                )
                for c in raw
                if c.get("text")
            ]
        except Exception as e:
            print(f"[hybrid] vector stage error: {e}")
            return []

    # ── Stage 2: Keyword search (Neo4j FULLTEXT) ──────────────────────────────

    def _stage_keyword(self, query: str, jurisdiction: str) -> List[RetrievalResult]:
        try:
            from graph.neo4j_client import neo4j_client
            if not neo4j_client._driver:
                return []

            jur_filter = "" if jurisdiction in ("both", "JP+US") else "AND n.jurisdiction = $jur"
            rows = neo4j_client.run_query(
                f"""
                CALL db.index.fulltext.queryNodes('legal_text', $query)
                YIELD node AS n, score
                WHERE coalesce(n.status, 'ACTIVE') = 'ACTIVE'
                  {jur_filter}
                RETURN n.node_id AS nid,
                       coalesce(n.text, n.title, '') AS text,
                       n.jurisdiction AS jur,
                       coalesce(n.article_no, '') AS article_no,
                       coalesce(n.title, '') AS law_name,
                       score
                ORDER BY score DESC
                LIMIT $limit
                """,
                {"query": query, "jur": jurisdiction, "limit": self.top_k_keyword},
            )
            return [
                RetrievalResult(
                    id=str(r["nid"] or _stable_id(r.get("text", ""))),
                    text=str(r.get("text", "")),
                    source="keyword",
                    score=float(r.get("score", 0.5)),
                    metadata={
                        "jurisdiction": r.get("jur", ""),
                        "law_name":     r.get("law_name", ""),
                        "article_no":   r.get("article_no", ""),
                        "status":       "ACTIVE",
                    },
                )
                for r in (rows or [])
                if r.get("text")
            ]
        except Exception as e:
            print(f"[hybrid] keyword stage error: {e}")
            return []

    # ── Stage 3: Graph BFS (2-hop) ────────────────────────────────────────────

    def _stage_graph_bfs(self, query: str, jurisdiction: str) -> List[RetrievalResult]:
        """Use fulltext anchors as seeds and expand 2 hops via APOC subgraphAll."""
        try:
            from graph.neo4j_client import neo4j_client
            if not neo4j_client._driver:
                return []

            # Get anchor IDs from fulltext
            jur_filter = "" if jurisdiction in ("both", "JP+US") else "AND n.jurisdiction = $jur"
            anchor_rows = neo4j_client.run_query(
                f"""
                CALL db.index.fulltext.queryNodes('legal_text', $query)
                YIELD node AS n, score
                WHERE coalesce(n.status, 'ACTIVE') = 'ACTIVE'
                  {jur_filter}
                RETURN n.node_id AS nid
                LIMIT 5
                """,
                {"query": query, "jur": jurisdiction},
            )
            if not anchor_rows:
                return []

            results: List[RetrievalResult] = []
            seen: set[str] = set()

            for row in anchor_rows:
                anchor_id = row.get("nid")
                if not anchor_id:
                    continue

                bfs_rows = neo4j_client.run_query(
                    """
                    MATCH (anchor {node_id: $anchor_id})
                    WHERE coalesce(anchor.status, 'ACTIVE') = 'ACTIVE'
                    CALL apoc.path.subgraphAll(anchor, {
                      relationshipFilter: "CITES|INTERPRETS|AMENDS|AMENDED_BY|IMPLEMENTS|HAS_PROVISION|GOVERNS",
                      maxLevel: 2
                    })
                    YIELD nodes
                    UNWIND nodes AS n
                    WHERE coalesce(n.status, 'ACTIVE') = 'ACTIVE'
                      AND n.node_id IS NOT NULL
                      AND (n.text IS NOT NULL OR n.title IS NOT NULL)
                    RETURN n.node_id AS nid,
                           coalesce(n.text, n.title, '') AS text,
                           n.jurisdiction AS jur,
                           coalesce(n.article_no, '') AS article_no,
                           coalesce(n.title, n.name, '') AS law_name
                    LIMIT $limit
                    """,
                    {"anchor_id": anchor_id, "limit": self.top_k_graph},
                )

                for bfs_row in (bfs_rows or []):
                    nid = str(bfs_row.get("nid", ""))
                    if not nid or nid in seen:
                        continue
                    seen.add(nid)
                    results.append(
                        RetrievalResult(
                            id=nid,
                            text=str(bfs_row.get("text", "")),
                            source="graph",
                            score=0.4,  # Base score; reranker will adjust
                            metadata={
                                "jurisdiction": bfs_row.get("jur", ""),
                                "law_name":     bfs_row.get("law_name", ""),
                                "article_no":   bfs_row.get("article_no", ""),
                                "status":       "ACTIVE",
                            },
                        )
                    )

            return results
        except Exception as e:
            print(f"[hybrid] graph BFS stage error: {e}")
            return []

    # ── Stage 4: CrossEncoder reranking ──────────────────────────────────────

    def _stage_rerank(self, query: str, candidates: List[RetrievalResult]) -> List[RetrievalResult]:
        """Rerank candidates using a CrossEncoder (ms-marco-MiniLM-L-6-v2).

        Falls back to original score order if sentence-transformers is unavailable
        or if the candidate list is too short to benefit from reranking.
        """
        if len(candidates) <= 1:
            return candidates

        try:
            encoder = self._get_cross_encoder()
            if encoder is None:
                candidates.sort(key=lambda x: x.score, reverse=True)
                return candidates

            pairs = [[query, c.text[:512]] for c in candidates]
            scores = encoder.predict(pairs)

            for candidate, score in zip(candidates, scores):
                candidate.score = float(score)

            candidates.sort(key=lambda x: x.score, reverse=True)
        except Exception as e:
            print(f"[hybrid] rerank error (non-fatal, using original scores): {e}")
            candidates.sort(key=lambda x: x.score, reverse=True)

        return candidates

    def _get_cross_encoder(self):
        """Lazy-load CrossEncoder. Returns None if not available."""
        if self._cross_encoder is not None:
            return self._cross_encoder
        try:
            from sentence_transformers import CrossEncoder
            self._cross_encoder = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512,
            )
            return self._cross_encoder
        except Exception as e:
            print(f"[hybrid] CrossEncoder unavailable: {e}")
            return None


# ─── Module-level singleton ───────────────────────────────────────────────────

_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def hybrid_search(
    query: str,
    jurisdiction: str,
    top_k: int = 5,
    use_graph: bool = True,
    use_vector: bool = True,
) -> List[dict]:
    """Convenience function: run hybrid retrieval and return plain dicts."""
    retriever = get_retriever()
    retriever.top_k_final = top_k
    results = retriever.retrieve(query, jurisdiction, use_graph=use_graph, use_vector=use_vector)
    return [r.to_dict() for r in results]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _stable_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]
