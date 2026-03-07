"""Neo4j client — connection management and Cypher query execution."""

import os
from typing import Optional

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "lexgraph_dev")


class Neo4jClient:
    """Thin wrapper around py2neo (Phase 0) or neo4j-driver (Phase 3).

    Phase 0/1: connection is stubbed out; methods return empty results.
    Phase 3: initialize real driver and implement Cypher queries.
    """

    def __init__(self):
        self._driver = None

    def connect(self) -> None:
        """Establish connection to Neo4j. Call on application startup."""
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self._driver.verify_connectivity()
        except Exception as e:
            # Non-fatal in Phase 0/1 — graph features are stubbed
            print(f"[neo4j_client] Connection failed (stub mode): {e}")

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def run_query(self, cypher: str, params: Optional[dict] = None) -> list:
        if not self._driver:
            return []
        with self._driver.session() as session:
            result = session.run(cypher, params or {})
            return [dict(record) for record in result]

    def traverse_subgraph(
        self,
        anchor_id: str,
        relationship_filter: str = "CITES|INTERPRETS|AMENDS|IMPLEMENTS|GOVERNS",
        max_level: int = 2,
    ) -> dict:
        """2-hop subgraph traversal using APOC path expansion."""
        cypher = """
        MATCH (anchor {node_id: $anchor_id})
        CALL apoc.path.subgraphAll(anchor, {
            relationshipFilter: $rel_filter,
            maxLevel: $max_level
        })
        YIELD nodes, relationships
        RETURN nodes, relationships
        LIMIT 50
        """
        rows = self.run_query(
            cypher,
            {"anchor_id": anchor_id, "rel_filter": relationship_filter, "max_level": max_level},
        )
        if not rows:
            return {"nodes": [], "relationships": []}
        return rows[0]


neo4j_client = Neo4jClient()
