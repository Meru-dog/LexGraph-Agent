"""Parameterized Cypher query templates for Graph RAG retrieval."""

# ─── Graph RAG — 2-hop subgraph expansion from anchor node ───────────────────
# Filters: only ACTIVE nodes are returned; AMENDED_BY edges traverse to latest version.

GRAPH_RAG_SUBGRAPH = """
MATCH (anchor {node_id: $anchor_id})
WHERE coalesce(anchor.status, 'ACTIVE') = 'ACTIVE'
CALL apoc.path.subgraphAll(anchor, {
  relationshipFilter: "CITES|INTERPRETS|AMENDS|AMENDED_BY|IMPLEMENTS|GOVERNS",
  maxLevel: 2
})
YIELD nodes, relationships
WITH [n IN nodes WHERE coalesce(n.status, 'ACTIVE') = 'ACTIVE'] AS active_nodes, relationships
RETURN active_nodes AS nodes, relationships
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
WHERE coalesce(c.status, 'ACTIVE') = 'ACTIVE'
RETURN c
ORDER BY c.date DESC
LIMIT 20
"""

# ─── Integrity checks (RDD §10.4) ────────────────────────────────────────────

# ① Orphaned nodes — no incoming or outgoing edges
INTEGRITY_ORPHANED_NODES = """
MATCH (n)
WHERE NOT (n)--()
  AND n:Statute OR n:Case OR n:Provision
RETURN labels(n) AS label, n.node_id AS node_id, n.title AS title
LIMIT 100
"""

# ② ACTIVE nodes that already have an AMENDED_BY edge (old version still ACTIVE)
INTEGRITY_ACTIVE_WITH_AMENDMENT = """
MATCH (old)-[:AMENDED_BY]->(new)
WHERE coalesce(old.status, 'ACTIVE') = 'ACTIVE'
RETURN labels(old) AS label,
       old.node_id AS old_id,
       old.title   AS old_title,
       new.node_id AS new_id,
       new.status  AS new_status
LIMIT 100
"""

# ③ Nodes with effective_date in the future but status = ACTIVE
INTEGRITY_FUTURE_EFFECTIVE_ACTIVE = """
MATCH (n)
WHERE coalesce(n.status, 'ACTIVE') = 'ACTIVE'
  AND n.effective_date IS NOT NULL
  AND n.effective_date > toString(date())
RETURN labels(n) AS label, n.node_id AS node_id, n.effective_date AS effective_date
LIMIT 100
"""

# ④ Cases that cite a law in text but have no CITES edge
INTEGRITY_MISSING_CITES_EDGES = """
MATCH (c:Case)
WHERE (c.text CONTAINS '第' OR c.summary CONTAINS 'U.S.C.')
  AND NOT (c)-[:CITES]->()
RETURN c.node_id AS case_id, c.docket_no AS docket_no, c.jurisdiction AS jurisdiction
LIMIT 100
"""
