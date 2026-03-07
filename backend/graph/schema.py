"""Neo4j schema — node labels, relationship types, and constraint definitions."""

# ─── Node Labels ──────────────────────────────────────────────────────────────

NODE_LABELS = {
    "Statute": {
        "properties": ["title", "article_no", "effective_date", "jurisdiction", "text", "source_url"],
        "index": ["title", "jurisdiction"],
    },
    "Case": {
        "properties": ["court", "docket_no", "date", "holding", "jurisdiction", "summary"],
        "index": ["docket_no", "jurisdiction"],
    },
    "Provision": {
        "properties": ["text", "parent_statute", "article_no", "section", "paragraph_no"],
        "index": ["article_no"],
    },
    "LegalConcept": {
        "properties": ["name", "domain", "definition", "aliases"],
        "index": ["name"],
    },
    "Entity": {
        "properties": ["name", "entity_type", "jurisdiction"],
        "index": ["name", "entity_type"],
    },
    "Regulation": {
        "properties": ["title", "issuer", "effective_date", "jurisdiction", "text"],
        "index": ["title", "jurisdiction"],
    },
    "Chunk": {
        "properties": ["text", "embedding_id", "source_doc_id", "position", "token_count"],
        "index": ["embedding_id", "source_doc_id"],
    },
}

# ─── Relationship Types ───────────────────────────────────────────────────────

RELATIONSHIP_TYPES = {
    "CITES": "Case → Case | Statute",
    "INTERPRETS": "Case → Provision",
    "AMENDS": "Statute → Statute",
    "IMPLEMENTS": "Regulation → Statute",
    "OVERRULES": "Case → Case",
    "ANALOGOUS_TO": "Concept → Concept",
    "GOVERNS": "Statute → LegalConcept",
    "INVOLVES": "Case → Entity",
    "CHUNK_OF": "Chunk → Statute | Case",
}

# ─── Constraint / Index Cypher Statements ────────────────────────────────────

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT statute_node_id IF NOT EXISTS FOR (s:Statute) REQUIRE s.node_id IS UNIQUE",
    "CREATE CONSTRAINT case_node_id IF NOT EXISTS FOR (c:Case) REQUIRE c.node_id IS UNIQUE",
    "CREATE CONSTRAINT provision_node_id IF NOT EXISTS FOR (p:Provision) REQUIRE p.node_id IS UNIQUE",
    "CREATE CONSTRAINT concept_node_id IF NOT EXISTS FOR (lc:LegalConcept) REQUIRE lc.node_id IS UNIQUE",
    "CREATE CONSTRAINT entity_node_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.node_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_embedding_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.embedding_id IS UNIQUE",
    "CREATE INDEX statute_title IF NOT EXISTS FOR (s:Statute) ON (s.title)",
    "CREATE INDEX statute_jurisdiction IF NOT EXISTS FOR (s:Statute) ON (s.jurisdiction)",
    "CREATE INDEX case_jurisdiction IF NOT EXISTS FOR (c:Case) ON (c.jurisdiction)",
    "CREATE FULLTEXT INDEX legal_text IF NOT EXISTS FOR (n:Statute|Case|Provision) ON EACH [n.text, n.title]",
]


def apply_schema(neo4j_client) -> None:
    """Apply all constraints and indexes to Neo4j. Idempotent."""
    for statement in SCHEMA_STATEMENTS:
        try:
            neo4j_client.run_query(statement)
        except Exception as e:
            print(f"[schema] Skipped statement (may already exist): {e}")
