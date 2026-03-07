"""Graph endpoints: GET /graph/search, GET /graph/node/{id}."""

from fastapi import APIRouter, Query, HTTPException

from tools.graph_search import graph_search

router = APIRouter(prefix="/graph", tags=["graph"])


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
