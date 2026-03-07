"""graph_search — fulltext search + 2-hop subgraph expansion via Neo4j."""

from typing import List


def graph_search(query: str, jurisdiction: str, node_types: List[str]) -> dict:
    """Search Neo4j with fulltext index, then expand a 2-hop subgraph.

    Falls back to empty result if Neo4j is not connected.
    """
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            raise RuntimeError("not connected")
        return _search(neo4j_client, query, jurisdiction, node_types)
    except Exception as e:
        print(f"[graph_search] error: {e}")
        return {"nodes": [], "relationships": [], "query": query, "jurisdiction": jurisdiction}


def _search(client, query: str, jurisdiction: str, node_types: List[str]) -> dict:
    # Step 1: fulltext search across Statute/Case/Provision text fields
    jur_filter = "" if jurisdiction in ("both", "JP+US") else "AND n.jurisdiction = $jurisdiction"
    rows = client.run_query(
        f"""
        CALL db.index.fulltext.queryNodes('legal_text', $query)
        YIELD node AS n, score
        WHERE any(label IN labels(n) WHERE label IN $node_types)
        {jur_filter}
        RETURN n, score
        ORDER BY score DESC
        LIMIT 10
        """,
        {"query": query, "jurisdiction": jurisdiction, "node_types": node_types},
    )

    if not rows:
        return {"nodes": [], "relationships": [], "query": query, "jurisdiction": jurisdiction}

    # Step 2: build anchor list and expand 1-hop neighborhood
    anchor_ids = [r["n"].get("node_id") for r in rows if r.get("n") and r["n"].get("node_id")]
    nodes = [_serialize_node(r["n"]) for r in rows if r.get("n")]
    relationships = []

    for anchor_id in anchor_ids[:5]:  # limit expansion to top-5 anchors
        sub = client.run_query(
            """
            MATCH (a {node_id: $id})-[r]-(b)
            RETURN a, type(r) AS rel_type, b
            LIMIT 20
            """,
            {"id": anchor_id},
        )
        for row in sub:
            if row.get("b"):
                node = _serialize_node(row["b"])
                if node not in nodes:
                    nodes.append(node)
            if row.get("rel_type") and row.get("a") and row.get("b"):
                relationships.append({
                    "from": anchor_id,
                    "to": row["b"].get("node_id", ""),
                    "type": row["rel_type"],
                })

    return {
        "nodes": nodes,
        "relationships": relationships,
        "query": query,
        "jurisdiction": jurisdiction,
    }


def _serialize_node(node) -> dict:
    """Convert a Neo4j Node object to a plain dict."""
    if isinstance(node, dict):
        return node
    try:
        d = dict(node)
        d["_labels"] = list(node.labels) if hasattr(node, "labels") else []
        return d
    except Exception:
        return {}
