"""graph_builder — create Document, Chunk, and Entity nodes in Neo4j."""

import time
from typing import List, Optional


def build_graph_nodes(
    chunks: List[dict],
    entities: List[dict],
    doc_id: str,
    document_type: str,
    filename: Optional[str] = None,
) -> dict:
    """Write Document node, Chunk nodes (with CHUNK_OF edges), and Entity nodes to Neo4j.

    Falls back gracefully if neo4j-driver is not connected.
    Returns a 'neo4j_stored' bool so callers can distinguish real writes from stubs.
    """
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            raise RuntimeError("Neo4j not connected")
        result = _write_to_neo4j(neo4j_client, chunks, entities, doc_id, document_type, filename)
        result["neo4j_stored"] = True
        return result
    except Exception as e:
        print(f"[graph_builder] Neo4j write skipped ({e})")
        return {
            "nodes_created": 0,
            "chunk_nodes": len(chunks),
            "entity_nodes": len(entities),
            "doc_id": doc_id,
            "neo4j_stored": False,
            "neo4j_skip_reason": str(e),
        }


def _write_to_neo4j(client, chunks, entities, doc_id, document_type, filename):
    now_ms = int(time.time() * 1000)

    # Upsert Document node
    client.run_query(
        """
        MERGE (d:Document {doc_id: $doc_id})
        SET d.document_type = $document_type,
            d.filename = $filename,
            d.created_at = timestamp(),
            d.status = coalesce(d.status, 'ACTIVE'),
            d.version = coalesce(d.version, 1),
            d.ingested_at = $ingested_at
        """,
        {"doc_id": doc_id, "document_type": document_type, "filename": filename or "", "ingested_at": now_ms},
    )

    # Upsert Chunk nodes + CHUNK_OF edges
    for chunk in chunks:
        client.run_query(
            """
            MERGE (c:Chunk {chunk_id: $chunk_id})
            SET c.doc_id = $doc_id,
                c.text = $text,
                c.chunk_index = $chunk_index,
                c.jurisdiction = $jurisdiction,
                c.status = coalesce(c.status, 'ACTIVE'),
                c.ingested_at = $ingested_at
            WITH c
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (c)-[:CHUNK_OF]->(d)
            """,
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "doc_id": doc_id,
                "text": chunk.get("text", ""),
                "chunk_index": chunk.get("chunk_index", 0),
                "jurisdiction": chunk.get("jurisdiction", ""),
                "ingested_at": now_ms,
            },
        )

    # Upsert Entity nodes + MENTIONED_IN edges
    for ent in entities:
        node_type = ent.get("node_type", "Entity")
        client.run_query(
            f"""
            MERGE (e:{node_type} {{name: $name}})
            SET e.spacy_label = $label
            WITH e
            MATCH (d:Document {{doc_id: $doc_id}})
            MERGE (e)-[:MENTIONED_IN]->(d)
            """,
            {"name": ent["text"], "label": ent.get("label", ""), "doc_id": doc_id},
        )

    return {
        "nodes_created": 1 + len(chunks) + len(entities),
        "chunk_nodes": len(chunks),
        "entity_nodes": len(entities),
        "doc_id": doc_id,
    }
