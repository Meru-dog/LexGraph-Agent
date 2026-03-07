"""Parameterized Cypher query templates for Graph RAG retrieval."""

# ─── Graph RAG — 2-hop subgraph expansion from anchor node ───────────────────

GRAPH_RAG_SUBGRAPH = """
MATCH (anchor {node_id: $anchor_id})
CALL apoc.path.subgraphAll(anchor, {
  relationshipFilter: "CITES|INTERPRETS|AMENDS|IMPLEMENTS|GOVERNS",
  maxLevel: 2
})
YIELD nodes, relationships
RETURN nodes, relationships
LIMIT 50
"""

# ─── Vector search anchor lookup ─────────────────────────────────────────────

FIND_CHUNKS_BY_EMBEDDING_IDS = """
MATCH (c:Chunk)
WHERE c.embedding_id IN $embedding_ids
RETURN c
"""

# ─── Statute lookup by article reference ─────────────────────────────────────

FIND_STATUTE_BY_ARTICLE = """
MATCH (s:Statute)-[:HAS_PROVISION]->(p:Provision)
WHERE p.article_no = $article_ref AND s.jurisdiction = $jurisdiction
RETURN s, p
LIMIT 1
"""

# ─── Case law by jurisdiction ─────────────────────────────────────────────────

FIND_CASES_BY_JURISDICTION = """
MATCH (c:Case {jurisdiction: $jurisdiction})
WHERE c.date >= $from_date
RETURN c
ORDER BY c.date DESC
LIMIT $limit
"""

# ─── Cross-jurisdictional concept alignment ──────────────────────────────────

FIND_ANALOGOUS_CONCEPTS = """
MATCH (jp:LegalConcept {jurisdiction: "JP"})-[:ANALOGOUS_TO]-(us:LegalConcept {jurisdiction: "US"})
RETURN jp.name AS jp_concept, us.name AS us_concept
LIMIT 50
"""

# ─── Entity → case involvement ────────────────────────────────────────────────

FIND_ENTITY_CASES = """
MATCH (e:Entity {name: $entity_name})<-[:INVOLVES]-(c:Case)
RETURN c
ORDER BY c.date DESC
LIMIT 20
"""
