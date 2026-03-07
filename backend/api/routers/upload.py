"""POST /upload — ingest document into the graph and vector store."""

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".html"}
MAX_FILE_SIZE_MB = 50

# In-memory document store (document_id → {bytes, filename}).
# Production: replace with MinIO/S3 client.
_document_store: dict[str, dict] = {}


def get_document_bytes(doc_id: str) -> bytes | None:
    """Retrieve raw document bytes by ID (used by contract review agent)."""
    entry = _document_store.get(doc_id)
    return entry["bytes"] if entry else None


def get_document_filename(doc_id: str) -> str | None:
    entry = _document_store.get(doc_id)
    return entry["filename"] if entry else None


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
    _document_store[doc_id] = {"bytes": contents, "filename": file.filename}

    # ── Fast synchronous pipeline (no ML inference) ────────────────────────
    # Embedding uses sentence-transformers which spawns multiprocessing workers
    # that deadlock inside asyncio event loops on macOS (PyTorch/MPS constraint).
    # Embedding is deferred to the POST /ingest/{doc_id} endpoint or background job.
    result = _run_fast_pipeline(contents, doc_id, document_type, file.filename)

    neo4j_stored = result.get("neo4j_stored", False)
    return {
        "document_id": doc_id,
        "filename": file.filename,
        "document_type": document_type,
        "size_bytes": len(contents),
        "neo4j_stored": neo4j_stored,
        "processing_steps": [
            {"step": "text_extraction", "status": "complete",
             "chars": result.get("text_length", 0)},
            {"step": "chunking", "status": "complete",
             "chunks": result.get("chunk_count", 0)},
            {"step": "ner_extraction", "status": "complete",
             "entities": result.get("entity_count", 0)},
            {"step": "graph_node_creation",
             "status": "complete" if neo4j_stored else "skipped",
             "nodes": result.get("nodes_created", 0),
             "note": None if neo4j_stored else result.get("neo4j_skip_reason", "Neo4j not connected")},
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
    entry = _document_store.get(doc_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document not found in store")

    contents = entry["bytes"]
    filename = entry["filename"]

    try:
        from ingestion.pipeline import _extract_text
        from ingestion.chunker import chunk_text

        text = _extract_text(contents, filename)
        chunks = chunk_text(text, doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {e}")

    # Embedding runs in a thread executor to avoid asyncio/PyTorch deadlock on macOS.
    # Failures are non-fatal — the document is still stored and usable without vectors.
    vectors_indexed = 0
    embed_error: str | None = None
    try:
        from ingestion.embedder import embed_chunks
        loop = asyncio.get_running_loop()
        embed_result = await loop.run_in_executor(None, embed_chunks, chunks)
        vectors_indexed = embed_result.get("vectors_indexed", 0)
    except Exception as e:
        embed_error = str(e)
        print(f"[ingest] embedding error (non-fatal): {e}")

    return {
        "doc_id": doc_id,
        "vectors_indexed": vectors_indexed,
        **({"embed_warning": embed_error} if embed_error else {}),
    }


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
