"""Metadata management for Neo4j nodes — amendment lifecycle and integrity checks.

Implements RDD §10.4: ACTIVE/ARCHIVED/DRAFT status, AMENDED_BY relationships,
and four graph integrity checks that run at startup and on-demand.
"""

import time
from typing import Optional, TypedDict, List


# ─── Type definitions ─────────────────────────────────────────────────────────

class NodeMetadata(TypedDict, total=False):
    status: str            # "ACTIVE" | "ARCHIVED" | "DRAFT"
    version: int           # incremented on each amendment
    effective_date: str    # YYYY-MM-DD
    amended_date: str      # YYYY-MM-DD or None
    expiry_date: str       # YYYY-MM-DD or None
    superseded_by: str     # node_id of replacement, or None
    ingested_at: int       # epoch ms
    last_verified: int     # epoch ms
    confidence: float      # 0.0–1.0


class IntegrityIssue(TypedDict):
    check: str
    severity: str          # "error" | "warning" | "info"
    node_id: str
    detail: str


# ─── Amendment manager ────────────────────────────────────────────────────────

class AmendmentManager:
    """Handles the amendment lifecycle: ACTIVE → ARCHIVED + new ACTIVE version."""

    def __init__(self, neo4j_client):
        self._client = neo4j_client

    def amend_node(
        self,
        old_node_id: str,
        new_node_id: str,
        new_properties: dict,
        amended_date: str,
    ) -> dict:
        """Archive old_node and create new_node with incremented version.

        Steps:
          1. Fetch old node version.
          2. SET old.status = ARCHIVED, old.amended_date = amended_date.
          3. MERGE new node with version = old.version + 1.
          4. Create AMENDED_BY edge: old → new.
        Returns {'old': old_node_id, 'new': new_node_id, 'version': new_version}.
        """
        # Fetch current version
        rows = self._client.run_query(
            "MATCH (n {node_id: $node_id}) RETURN coalesce(n.version, 1) AS v",
            {"node_id": old_node_id},
        )
        old_version = rows[0]["v"] if rows else 1
        new_version = old_version + 1

        # Archive old node
        self._client.run_query(
            """
            MATCH (n {node_id: $node_id})
            SET n.status = 'ARCHIVED',
                n.amended_date = $amended_date,
                n.superseded_by = $new_node_id
            """,
            {"node_id": old_node_id, "amended_date": amended_date, "new_node_id": new_node_id},
        )

        # Create new node (label-agnostic via MERGE on generic node — caller should
        # use label-specific Cypher for real ingestion; this is the lifecycle hook)
        self._client.run_query(
            """
            MATCH (old {node_id: $old_id})
            MERGE (new {node_id: $new_id})
            SET new += $props,
                new.version = $version,
                new.status = 'ACTIVE',
                new.ingested_at = $now
            MERGE (old)-[:AMENDED_BY]->(new)
            """,
            {
                "old_id": old_node_id,
                "new_id": new_node_id,
                "props": new_properties,
                "version": new_version,
                "now": int(time.time() * 1000),
            },
        )

        return {"old": old_node_id, "new": new_node_id, "version": new_version}

    def get_latest_version(self, node_id: str) -> Optional[str]:
        """Follow AMENDED_BY chain to the current ACTIVE node_id."""
        rows = self._client.run_query(
            """
            MATCH path = (start {node_id: $node_id})-[:AMENDED_BY*0..]->(latest)
            WHERE NOT (latest)-[:AMENDED_BY]->()
            RETURN latest.node_id AS node_id
            LIMIT 1
            """,
            {"node_id": node_id},
        )
        return rows[0]["node_id"] if rows else None


# ─── Integrity checks ─────────────────────────────────────────────────────────

def check_orphaned_nodes(client) -> List[IntegrityIssue]:
    """① Return Statute/Case/Provision nodes with no edges."""
    from graph.cypher_queries import INTEGRITY_ORPHANED_NODES
    rows = client.run_query(INTEGRITY_ORPHANED_NODES)
    return [
        IntegrityIssue(
            check="orphaned_node",
            severity="warning",
            node_id=r.get("node_id", ""),
            detail=f"label={r.get('label')}, title={r.get('title')}",
        )
        for r in (rows or [])
    ]


def check_active_with_amendment(client) -> List[IntegrityIssue]:
    """② Return ACTIVE nodes that have an AMENDED_BY edge (should be ARCHIVED)."""
    from graph.cypher_queries import INTEGRITY_ACTIVE_WITH_AMENDMENT
    rows = client.run_query(INTEGRITY_ACTIVE_WITH_AMENDMENT)
    return [
        IntegrityIssue(
            check="active_with_amendment",
            severity="error",
            node_id=r.get("old_id", ""),
            detail=f"superseded by {r.get('new_id')} but still ACTIVE",
        )
        for r in (rows or [])
    ]


def check_future_effective_active(client) -> List[IntegrityIssue]:
    """③ Return ACTIVE nodes whose effective_date is in the future."""
    from graph.cypher_queries import INTEGRITY_FUTURE_EFFECTIVE_ACTIVE
    rows = client.run_query(INTEGRITY_FUTURE_EFFECTIVE_ACTIVE)
    return [
        IntegrityIssue(
            check="future_effective_active",
            severity="warning",
            node_id=r.get("node_id", ""),
            detail=f"effective_date={r.get('effective_date')} is in the future",
        )
        for r in (rows or [])
    ]


def check_missing_cites_edges(client) -> List[IntegrityIssue]:
    """④ Return Cases that reference a statute in text but have no CITES edge."""
    from graph.cypher_queries import INTEGRITY_MISSING_CITES_EDGES
    rows = client.run_query(INTEGRITY_MISSING_CITES_EDGES)
    return [
        IntegrityIssue(
            check="missing_cites_edge",
            severity="info",
            node_id=r.get("case_id", ""),
            detail=f"docket={r.get('docket_no')}, jurisdiction={r.get('jurisdiction')}",
        )
        for r in (rows or [])
    ]


def run_all_integrity_checks(client) -> dict:
    """Run all four integrity checks and return a summary dict."""
    if not client._driver:
        return {"skipped": True, "reason": "Neo4j not connected"}

    results = {
        "orphaned_nodes": check_orphaned_nodes(client),
        "active_with_amendment": check_active_with_amendment(client),
        "future_effective_active": check_future_effective_active(client),
        "missing_cites_edges": check_missing_cites_edges(client),
    }
    total_errors = sum(
        len([i for i in issues if i["severity"] == "error"])
        for issues in results.values()
    )
    total_warnings = sum(
        len([i for i in issues if i["severity"] == "warning"])
        for issues in results.values()
    )
    results["summary"] = {
        "errors": total_errors,
        "warnings": total_warnings,
        "passed": total_errors == 0,
    }
    return results
