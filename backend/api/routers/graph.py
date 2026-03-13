"""Graph endpoints: GET /graph/search, GET /graph/node/{id}."""

from fastapi import APIRouter, Query, HTTPException

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
