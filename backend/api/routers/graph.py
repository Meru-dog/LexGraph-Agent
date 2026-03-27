"""Graph endpoints: GET /graph/search, GET /graph/node/{id}."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from tools.graph_search import graph_search

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats")
async def graph_stats():
    """Return live node/relationship counts from Neo4j."""
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            return {"connected": False, "nodes": 0, "relationships": 0, "by_label": {}}
        with neo4j_client._driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            label_rows = session.run(
                "CALL db.labels() YIELD label "
                "CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) AS c', {}) YIELD value "
                "RETURN label, value.c AS c"
            )
            by_label = {row["label"]: row["c"] for row in label_rows}
        return {"connected": True, "nodes": node_count, "relationships": rel_count, "by_label": by_label}
    except Exception:
        # apoc may not be available — fall back to simple counts
        try:
            from graph.neo4j_client import neo4j_client
            with neo4j_client._driver.session() as session:
                node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            return {"connected": True, "nodes": node_count, "relationships": rel_count, "by_label": {}}
        except Exception as e:
            return {"connected": False, "nodes": 0, "relationships": 0, "by_label": {}, "error": str(e)}


@router.get("/sample")
async def sample_graph(limit: int = Query(default=60, ge=10, le=200)):
    """Return a sample subgraph (nodes + relationships) for force-directed visualization.

    Excludes raw Chunk nodes (which contain unreadable embedding text) and shows only
    meaningful semantic nodes: Statute, Case, Provision, LegalConcept, Entity, Document.
    """
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            return _mock_graph()
        with neo4j_client._driver.session() as session:
            # Exclude Chunk nodes — they contain raw text and clutter the graph
            node_rows = list(session.run(
                """
                MATCH (n)
                WHERE NOT n:Chunk
                RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props
                LIMIT $limit
                """,
                {"limit": limit},
            ))
            nodes = []
            eid_to_id: dict = {}
            for row in node_rows:
                props = dict(row["props"])
                nid = str(props.get("node_id") or row["eid"])
                labels = list(row["labels"])
                # Build a clean display label (never show raw text blobs)
                props["_id"] = nid
                props["_labels"] = labels
                props["_display_label"] = _make_display_label(props, labels)
                # Strip the raw text field so it doesn't leak to the frontend
                props.pop("text", None)
                nodes.append(props)
                eid_to_id[row["eid"]] = nid

            eids = [row["eid"] for row in node_rows]
            rel_rows = list(session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE elementId(a) IN $eids AND elementId(b) IN $eids
                  AND NOT a:Chunk AND NOT b:Chunk
                RETURN type(r) AS type,
                       coalesce(a.node_id, elementId(a)) AS src,
                       coalesce(b.node_id, elementId(b)) AS tgt
                LIMIT 300
                """,
                {"eids": eids},
            ))
            rels = [{"type": r["type"], "source": str(r["src"]), "target": str(r["tgt"])} for r in rel_rows]
        return {"nodes": nodes, "relationships": rels, "connected": True}
    except Exception as e:
        print(f"[graph/sample] {e}")
        return _mock_graph()


def _make_display_label(props: dict, labels: list) -> str:
    """Create a short, human-readable display label for a graph node."""
    # Prefer explicit name/title fields
    label = props.get("name") or props.get("title") or props.get("node_id", "")
    if label:
        return str(label)[:40]
    # For Document nodes, use filename
    if "Document" in labels:
        return str(props.get("filename") or props.get("doc_id", "Document"))[:30]
    # For Entity nodes, use spacy_label + name
    if "Entity" in labels:
        spacy = props.get("spacy_label", "")
        return f"{spacy}: {props.get('name', '')}"[:30] if spacy else str(props.get("name", "Entity"))[:30]
    # Fallback: use the node_id/eid but truncate
    return str(props.get("node_id", "Node"))[:20]


def _mock_graph() -> dict:
    """Demo graph used when Neo4j is unavailable."""
    nodes = [
        {"_id": "jp_companies_act", "_labels": ["Statute"], "name": "会社法", "title": "Companies Act", "jurisdiction": "JP"},
        {"_id": "jp_fiea", "_labels": ["Statute"], "name": "金商法", "title": "FIEA", "jurisdiction": "JP"},
        {"_id": "jp_civil_code", "_labels": ["Statute"], "name": "民法", "title": "Civil Code", "jurisdiction": "JP"},
        {"_id": "us_dgcl", "_labels": ["Statute"], "name": "DGCL", "title": "Delaware Corp Law", "jurisdiction": "US"},
        {"_id": "us_sec_act", "_labels": ["Statute"], "name": "SEA 1934", "title": "Securities Exchange Act", "jurisdiction": "US"},
        {"_id": "us_ucc", "_labels": ["Statute"], "name": "UCC Art.2", "title": "Uniform Commercial Code", "jurisdiction": "US"},
        {"_id": "jp_corp_gov", "_labels": ["LegalConcept"], "name": "Corporate Gov.", "jurisdiction": "JP"},
        {"_id": "us_fiduciary", "_labels": ["LegalConcept"], "name": "Fiduciary Duty", "jurisdiction": "US"},
        {"_id": "jp_disclosure", "_labels": ["LegalConcept"], "name": "Disclosure (JP)", "jurisdiction": "JP"},
        {"_id": "us_disclosure", "_labels": ["LegalConcept"], "name": "Disclosure (US)", "jurisdiction": "US"},
        {"_id": "jp_art_330", "_labels": ["Provision"], "name": "Art.330", "title": "Director Obligations", "jurisdiction": "JP"},
        {"_id": "jp_art_362", "_labels": ["Provision"], "name": "Art.362", "title": "Board Duties", "jurisdiction": "JP"},
        {"_id": "us_rule_10b5", "_labels": ["Provision"], "name": "Rule 10b-5", "title": "Anti-Fraud Rule", "jurisdiction": "US"},
        {"_id": "us_sec_16", "_labels": ["Provision"], "name": "§16", "title": "Insider Reporting", "jurisdiction": "US"},
        {"_id": "corp_techcorp", "_labels": ["Entity"], "name": "TechCorp KK", "jurisdiction": "JP"},
        {"_id": "corp_investco", "_labels": ["Entity"], "name": "InvestCo LLC", "jurisdiction": "US"},
    ]
    rels = [
        {"source": "jp_art_330", "target": "jp_companies_act", "type": "PART_OF"},
        {"source": "jp_art_362", "target": "jp_companies_act", "type": "PART_OF"},
        {"source": "us_rule_10b5", "target": "us_sec_act", "type": "PART_OF"},
        {"source": "us_sec_16", "target": "us_sec_act", "type": "PART_OF"},
        {"source": "jp_art_330", "target": "jp_corp_gov", "type": "IMPLEMENTS"},
        {"source": "jp_art_362", "target": "jp_corp_gov", "type": "IMPLEMENTS"},
        {"source": "us_rule_10b5", "target": "us_fiduciary", "type": "IMPLEMENTS"},
        {"source": "us_fiduciary", "target": "us_dgcl", "type": "GOVERNED_BY"},
        {"source": "jp_corp_gov", "target": "us_fiduciary", "type": "ANALOGOUS_TO"},
        {"source": "jp_disclosure", "target": "jp_fiea", "type": "GOVERNED_BY"},
        {"source": "us_disclosure", "target": "us_sec_act", "type": "GOVERNED_BY"},
        {"source": "jp_disclosure", "target": "us_disclosure", "type": "ANALOGOUS_TO"},
        {"source": "corp_techcorp", "target": "jp_companies_act", "type": "GOVERNED_BY"},
        {"source": "corp_investco", "target": "us_dgcl", "type": "GOVERNED_BY"},
        {"source": "jp_civil_code", "target": "jp_companies_act", "type": "CITES"},
        {"source": "us_ucc", "target": "us_sec_act", "type": "CITES"},
        {"source": "corp_techcorp", "target": "corp_investco", "type": "RELATED_TO"},
    ]
    return {"nodes": nodes, "relationships": rels, "connected": False}


@router.get("/quality")
async def graph_quality():
    """Graph quality dashboard metrics (RDD §10.6).

    Returns:
      node_counts        — total + by-label breakdown
      archived_ratio     — fraction of ARCHIVED nodes
      orphaned_count     — nodes with no edges
      unverified_count   — nodes where last_verified > 90 days ago
      unverified_nodes   — sample of those nodes (node_id, law_name, last_verified)
      stale_laws         — law_name + last_verified for Statute nodes (sorted oldest first)
    """
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            return {"connected": False}
        with neo4j_client._driver.session() as session:
            # Total + ARCHIVED counts
            totals = session.run(
                "MATCH (n) RETURN count(n) AS total, "
                "sum(CASE WHEN n.status = 'ARCHIVED' THEN 1 ELSE 0 END) AS archived"
            ).single()
            total = totals["total"] or 0
            archived = totals["archived"] or 0
            archived_ratio = round(archived / total, 4) if total else 0.0

            # By-label breakdown (ACTIVE only)
            label_rows = list(session.run(
                """
                MATCH (n)
                WHERE n.status IS NULL OR n.status = 'ACTIVE'
                UNWIND labels(n) AS lbl
                RETURN lbl, count(*) AS c
                ORDER BY c DESC
                """
            ))
            by_label = {r["lbl"]: r["c"] for r in label_rows}

            # Orphaned node count
            orphaned = session.run(
                "MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c"
            ).single()["c"]

            # Unverified nodes (last_verified > 90 days ago or null)
            unverified_rows = list(session.run(
                """
                MATCH (n)
                WHERE n.status IS NULL OR n.status = 'ACTIVE'
                AND (
                    n.last_verified IS NULL
                    OR date(n.last_verified) < date() - duration({days: 90})
                )
                RETURN n.node_id AS node_id, n.law_name AS law_name,
                       n.last_verified AS last_verified,
                       labels(n) AS node_labels
                ORDER BY n.last_verified ASC
                LIMIT 20
                """
            ))
            unverified_nodes = [
                {
                    "node_id": r["node_id"],
                    "law_name": r["law_name"],
                    "last_verified": r["last_verified"],
                    "labels": list(r["node_labels"]),
                }
                for r in unverified_rows
            ]
            unverified_count = session.run(
                """
                MATCH (n)
                WHERE (n.status IS NULL OR n.status = 'ACTIVE')
                AND (
                    n.last_verified IS NULL
                    OR date(n.last_verified) < date() - duration({days: 90})
                )
                RETURN count(n) AS c
                """
            ).single()["c"]

            # Statute nodes sorted by last_verified (stale laws list)
            stale_rows = list(session.run(
                """
                MATCH (n:Statute)
                WHERE n.status IS NULL OR n.status = 'ACTIVE'
                RETURN n.node_id AS node_id, n.name AS name,
                       n.last_verified AS last_verified,
                       n.jurisdiction AS jurisdiction
                ORDER BY n.last_verified ASC
                LIMIT 10
                """
            ))
            stale_laws = [
                {
                    "node_id": r["node_id"],
                    "name": r["name"],
                    "last_verified": r["last_verified"],
                    "jurisdiction": r["jurisdiction"],
                }
                for r in stale_rows
            ]

        return {
            "connected": True,
            "total_nodes": total,
            "archived_nodes": archived,
            "archived_ratio": archived_ratio,
            "active_by_label": by_label,
            "orphaned_count": orphaned,
            "unverified_count": unverified_count,
            "unverified_nodes": unverified_nodes,
            "stale_laws": stale_laws,
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/integrity")
async def graph_integrity():
    """Run all four metadata integrity checks from RDD §10.4.

    Returns a summary dict with errors/warnings counts and per-check results.
    """
    try:
        from graph.neo4j_client import neo4j_client
        from graph.metadata import run_all_integrity_checks
        return run_all_integrity_checks(neo4j_client)
    except Exception as e:
        return {"skipped": True, "reason": str(e)}


class AmendmentCheckRequest(BaseModel):
    law_ids: Optional[list[str]] = None   # None → check all TRACKED_LAWS
    since_date: Optional[str] = None      # ISO date, default = 90 days ago
    auto_archive: bool = False            # If True, archive amended nodes in Neo4j


@router.post("/check-amendments")
async def check_amendments(request: AmendmentCheckRequest, background_tasks: BackgroundTasks):
    """Check e-Gov API for law amendments (RDD §10.3 / Phase 6).

    Triggers a live query to https://laws.e-gov.go.jp for tracked laws.
    If auto_archive=True, archives amended Neo4j nodes in the background.
    """
    try:
        from tools.egov_monitor import check_amendments as _check
        result = _check(law_ids=request.law_ids, since_date=request.since_date)

        if request.auto_archive and result.get("amended_count", 0) > 0:
            from tools.egov_monitor import archive_amended_nodes
            background_tasks.add_task(archive_amended_nodes, result)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_graph(
    q: str = Query(..., description="Search query"),
    jurisdiction: str = Query(default="JP", description="JP | US | JP+US"),
    node_types: str = Query(default="Statute,Case,LegalConcept", description="Comma-separated node types"),
):
    types = [t.strip() for t in node_types.split(",")]
    result = graph_search(query=q, jurisdiction=jurisdiction, node_types=types)
    return result


@router.get("/node/{node_id}")
async def get_node(node_id: str, hops: int = Query(default=2, ge=1, le=3)):
    """Fetch a single node and its N-hop neighborhood via Neo4j traversal."""
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            return {"node_id": node_id, "hops": hops, "nodes": [], "relationships": []}

        subgraph = neo4j_client.traverse_subgraph(
            anchor_id=node_id,
            max_level=hops,
        )

        # Serialize Neo4j Node/Relationship objects to plain dicts
        nodes = [_serialize(n) for n in subgraph.get("nodes", [])]
        rels = [_serialize_rel(r) for r in subgraph.get("relationships", [])]

        return {
            "node_id": node_id,
            "hops": hops,
            "nodes": nodes,
            "relationships": rels,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[graph/node] error: {e}")
        return {"node_id": node_id, "hops": hops, "nodes": [], "relationships": []}


def _serialize(node) -> dict:
    if isinstance(node, dict):
        return node
    try:
        d = dict(node)
        d["_labels"] = list(node.labels) if hasattr(node, "labels") else []
        return d
    except Exception:
        return {}


def _serialize_rel(rel) -> dict:
    if isinstance(rel, dict):
        return rel
    try:
        return {
            "type": rel.type if hasattr(rel, "type") else str(rel),
            "start": rel.start_node.get("node_id", "") if hasattr(rel, "start_node") else "",
            "end": rel.end_node.get("node_id", "") if hasattr(rel, "end_node") else "",
            **dict(rel),
        }
    except Exception:
        return {}
