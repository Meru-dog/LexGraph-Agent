"""Neo4j schema — node labels, relationship types, and constraint definitions.

Metadata fields added (Phase 0 — required for metadata management):
  status         ACTIVE | ARCHIVED | DRAFT
  version        int (incremented on each amendment)
  effective_date date string (YYYY-MM-DD)
  amended_date   date string (YYYY-MM-DD) or None
  superseded_by  node_id of the replacement node, or None
  ingested_at    epoch ms timestamp
  last_verified  epoch ms timestamp
  confidence     float 0.0–1.0
"""

# ─── Node Labels ──────────────────────────────────────────────────────────────

NODE_LABELS = {
    "Statute": {
        "properties": [
            "title", "article_no", "effective_date", "jurisdiction",
            "text", "source_url",
            # Metadata management (Phase 0)
            "status", "version", "amended_date", "expiry_date",
            "superseded_by", "ingested_at", "last_verified", "confidence",
        ],
        "index": ["title", "jurisdiction", "status"],
    },
    "Case": {
        "properties": [
            "court", "docket_no", "date", "holding", "jurisdiction", "summary",
            # Metadata management
            "status", "version", "ingested_at", "last_verified", "confidence",
        ],
        "index": ["docket_no", "jurisdiction", "status"],
    },
    "Provision": {
        "properties": [
            "text", "parent_statute", "article_no", "section", "paragraph_no",
            # Metadata management
            "status", "version", "effective_date", "superseded_by",
            "ingested_at", "last_verified",
        ],
        "index": ["article_no", "status"],
    },
    "LegalConcept": {
        "properties": ["name", "domain", "definition", "aliases"],
        "index": ["name"],
    },
    "LegalElement": {
        "properties": ["name", "element_type"],
        "index": ["name"],
    },
    "Entity": {
        "properties": ["name", "entity_type", "jurisdiction"],
        "index": ["name", "entity_type"],
    },
    "Regulation": {
        "properties": [
            "title", "issuer", "effective_date", "jurisdiction", "text",
            "status", "version",
        ],
        "index": ["title", "jurisdiction", "status"],
    },
    "Chunk": {
        "properties": ["text", "embedding_id", "source_doc_id", "position", "token_count"],
        "index": ["embedding_id", "source_doc_id"],
    },
}

# ─── Relationship Types ───────────────────────────────────────────────────────

RELATIONSHIP_TYPES = {
    # Phase 0 — core
    "CITES":      "Case → Case | Statute",
    "INTERPRETS": "Case → Provision",
    "AMENDS":     "Statute → Statute",
    "AMENDED_BY": "Statute → Statute  (points to the new version; mandatory for metadata management)",
    "CHUNK_OF":   "Chunk → Statute | Case",
    # Phase 1
    "IMPLEMENTS": "Regulation → Statute",
    "OVERRULES":  "Case → Case",
    "HAS_PROVISION": "Statute → Provision",
    # Phase 3
    "REQUIRES_PROOF_OF": "Provision → LegalElement",
    "GOVERNED_BY":       "LegalConcept → Statute",
    "INVOLVES":          "Case → Entity",
    "MENTIONED_IN":      "Entity → Document",
    "GOVERNS":           "Provision → LegalConcept",
    # Phase 4 — requires legal review before creating
    "ANALOGOUS_TO": "Concept → Concept  (JP ↔ US; must be human-reviewed)",
    "CONFLICT_WITH": "Provision → Provision",
}

# ─── Constraint / Index Cypher Statements ─────────────────────────────────────

SCHEMA_STATEMENTS = [
    # Uniqueness constraints
    "CREATE CONSTRAINT statute_node_id IF NOT EXISTS FOR (s:Statute) REQUIRE s.node_id IS UNIQUE",
    "CREATE CONSTRAINT case_node_id IF NOT EXISTS FOR (c:Case) REQUIRE c.node_id IS UNIQUE",
    "CREATE CONSTRAINT provision_node_id IF NOT EXISTS FOR (p:Provision) REQUIRE p.node_id IS UNIQUE",
    "CREATE CONSTRAINT concept_node_id IF NOT EXISTS FOR (lc:LegalConcept) REQUIRE lc.node_id IS UNIQUE",
    "CREATE CONSTRAINT element_node_id IF NOT EXISTS FOR (le:LegalElement) REQUIRE le.node_id IS UNIQUE",
    "CREATE CONSTRAINT entity_node_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.node_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_embedding_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.embedding_id IS UNIQUE",
    # Search indexes
    "CREATE INDEX statute_title IF NOT EXISTS FOR (s:Statute) ON (s.title)",
    "CREATE INDEX statute_jurisdiction IF NOT EXISTS FOR (s:Statute) ON (s.jurisdiction)",
    "CREATE INDEX statute_status IF NOT EXISTS FOR (s:Statute) ON (s.status)",
    "CREATE INDEX case_jurisdiction IF NOT EXISTS FOR (c:Case) ON (c.jurisdiction)",
    "CREATE INDEX case_status IF NOT EXISTS FOR (c:Case) ON (c.status)",
    "CREATE INDEX provision_status IF NOT EXISTS FOR (p:Provision) ON (p.status)",
    # Full-text index for keyword search
    "CREATE FULLTEXT INDEX legal_text IF NOT EXISTS FOR (n:Statute|Case|Provision) ON EACH [n.text, n.title]",
]


def apply_schema(neo4j_client) -> None:
    """Apply all constraints and indexes to Neo4j. Idempotent."""
    for statement in SCHEMA_STATEMENTS:
        try:
            neo4j_client.run_query(statement)
        except Exception as e:
            print(f"[schema] Skipped (may already exist): {e}")
