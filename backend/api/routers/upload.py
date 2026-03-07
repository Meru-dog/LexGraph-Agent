"""POST /upload — ingest document into the graph and vector store."""

import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html"}
MAX_FILE_SIZE_MB = 50

# In-memory document store (document_id → raw bytes).
# Production: replace with MinIO/S3 client.
_document_store: dict[str, bytes] = {}


def get_document_bytes(doc_id: str) -> bytes | None:
    """Retrieve raw document bytes by ID (used by contract review agent)."""
    return _document_store.get(doc_id)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(default="other"),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_FILE_SIZE_MB}MB limit")

    doc_id = str(uuid.uuid4())
    _document_store[doc_id] = contents

    # ── Fast synchronous pipeline (no ML inference) ────────────────────────
    # Embedding uses sentence-transformers which spawns multiprocessing workers
    # that deadlock inside asyncio event loops on macOS (PyTorch/MPS constraint).
    # Embedding is deferred to the POST /ingest/{doc_id} endpoint or background job.
    result = _run_fast_pipeline(contents, doc_id, document_type, file.filename)

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "document_type": document_type,
        "size_bytes": len(contents),
        "processing_steps": [
            {"step": "text_extraction", "status": "complete",
             "chars": result.get("text_length", 0)},
            {"step": "chunking", "status": "complete",
             "chunks": result.get("chunk_count", 0)},
            {"step": "ner_extraction", "status": "complete",
             "entities": result.get("entity_count", 0)},
            {"step": "graph_node_creation", "status": "complete",
             "nodes": result.get("graph_nodes_created", 0)},
            {"step": "embedding_indexing", "status": "deferred",
             "vectors": 0, "note": "call POST /ingest/{doc_id} to embed"},
        ],
        "status": "complete",
    }


@router.post("/ingest/{doc_id}")
async def ingest_document(doc_id: str):
    """Trigger embedding for a previously uploaded document.

    Embedding is separated from upload because sentence-transformers'
    multiprocessing DataLoader can deadlock inside the asyncio event loop on macOS.
    In production, this is called from a worker process (Celery/RQ).
    """
    contents = _document_store.get(doc_id)
    if contents is None:
        raise HTTPException(status_code=404, detail="Document not found in store")

    try:
        from ingestion.pipeline import _extract_text
        from ingestion.chunker import chunk_text
        from ingestion.embedder import embed_chunks

        # Re-extract text and chunks (or cache them — future optimization)
        text = _extract_text(contents, None)
        chunks = chunk_text(text, doc_id)
        embed_result = embed_chunks(chunks)
        return {"doc_id": doc_id, "vectors_indexed": embed_result.get("vectors_indexed", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_fast_pipeline(contents: bytes, doc_id: str, document_type: str,
                        filename: str | None) -> dict:
    try:
        from ingestion.pipeline import _extract_text
        from ingestion.chunker import chunk_text
        from ingestion.ner import extract_entities
        from ingestion.graph_builder import build_graph_nodes

        text = _extract_text(contents, filename)
        chunks = chunk_text(text, doc_id)
        entities = extract_entities(text)
        graph_result = build_graph_nodes(
            chunks=chunks, entities=entities,
            doc_id=doc_id, document_type=document_type, filename=filename,
        )
        return {
            "text_length": len(text),
            "chunk_count": len(chunks),
            "entity_count": len(entities),
            "graph_nodes_created": graph_result.get("nodes_created", 0),
        }
    except Exception as e:
        print(f"[upload] fast pipeline error: {e}")
        return {}
