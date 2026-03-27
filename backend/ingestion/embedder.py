"""embedder — multilingual-e5-large embedding generation with Supabase pgvector storage.

Primary store: Supabase pgvector (chunks table, vector(1024)).
Fallback:      In-memory numpy dict (for development without Supabase configured).

Vector search uses the match_chunks() RPC function defined in
supabase/migrations/001_initial_schema.sql which filters by:
  - status = 'ACTIVE'          (excludes ARCHIVED / repealed statutes)
  - jurisdiction               (JP | US)
  - effective_date <= today    (excludes statutes not yet in force)
"""

import os
import threading
from typing import List

MODEL_NAME = "intfloat/multilingual-e5-large"
VECTOR_DIM = 1024  # multilingual-e5-large output dimension

_model = None
_lock = threading.Lock()

# In-memory fallback store: chunk_id → {text, embedding (list), jurisdiction, ...}
_mem_store: dict = {}


# ── Public API ────────────────────────────────────────────────────────────────

def embed_chunks(chunks: List[dict]) -> dict:
    """Embed chunks with multilingual-e5-large and persist to Supabase pgvector.

    Each chunk dict should contain:
        chunk_id, doc_id, text, jurisdiction
    Optional: source_type, law_name, article_no, status, effective_date

    Falls back to in-memory store if Supabase is not configured.
    """
    if not chunks:
        return {"vectors_indexed": 0, "model": MODEL_NAME}

    model = _get_model()
    if model is None:
        return {"vectors_indexed": len(chunks), "model": f"{MODEL_NAME} (stub — model unavailable)"}

    texts = [f"passage: {c['text']}" for c in chunks]
    embeddings = model.encode(
        texts, batch_size=32, normalize_embeddings=True,
        show_progress_bar=False, num_workers=0,
    )

    from db.supabase_client import is_supabase_configured

    if is_supabase_configured():
        return _upsert_to_pgvector(chunks, embeddings)
    else:
        return _store_in_memory(chunks, embeddings)


def search_chunks(
    query: str,
    jurisdiction: str,
    top_k: int = 5,
    status: str = "ACTIVE",
) -> List[dict]:
    """Retrieve top-k semantically similar chunks.

    Filters: status=ACTIVE, jurisdiction, effective_date <= today.
    Returns empty list if no store is available or no results found.
    """
    model = _get_model()
    if model is None:
        return []

    query_vec = model.encode(
        [f"query: {query}"], normalize_embeddings=True, show_progress_bar=False
    )[0]

    from db.supabase_client import is_supabase_configured

    if is_supabase_configured():
        return _search_pgvector(query_vec, jurisdiction, top_k, status)
    else:
        return _search_memory(query_vec, jurisdiction, top_k)


# ── pgvector (Supabase) ───────────────────────────────────────────────────────

def _upsert_to_pgvector(chunks: List[dict], embeddings) -> dict:
    """Upsert chunks + embeddings into Supabase chunks table."""
    from db.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        return _store_in_memory(chunks, embeddings)

    rows = []
    for chunk, emb in zip(chunks, embeddings):
        rows.append({
            "chunk_id":       chunk.get("chunk_id"),
            "document_id":    chunk.get("doc_id"),
            "text":           chunk.get("text", ""),
            "embedding":      emb.tolist(),
            "source_type":    chunk.get("source_type", "Other"),
            "law_name":       chunk.get("law_name"),
            "article_no":     chunk.get("article_no"),
            "jurisdiction":   chunk.get("jurisdiction", ""),
            "status":         chunk.get("status", "ACTIVE"),
            "effective_date": chunk.get("effective_date"),
            "version":        chunk.get("version", 1),
        })

    try:
        # Upsert on chunk_id so re-ingesting the same document is idempotent
        client.table("chunks").upsert(rows, on_conflict="chunk_id").execute()
        print(f"[embedder] pgvector: upserted {len(rows)} chunks")
        return {"vectors_indexed": len(rows), "model": MODEL_NAME}
    except Exception as e:
        print(f"[embedder] pgvector upsert failed ({e}), falling back to memory")
        return _store_in_memory(chunks, embeddings)


def _search_pgvector(
    query_vec,
    jurisdiction: str,
    top_k: int,
    status: str,
) -> List[dict]:
    """Call match_chunks() RPC on Supabase for similarity search with metadata filter."""
    from db.supabase_client import get_supabase_client
    client = get_supabase_client()
    if not client:
        return _search_memory(query_vec, jurisdiction, top_k)

    try:
        params = {
            "query_embedding":      query_vec.tolist(),
            "match_count":          top_k,
            "filter_jurisdiction":  jurisdiction or None,
            "filter_status":        status,
        }
        result = client.rpc("match_chunks", params).execute()
        rows = result.data or []
        return [
            {
                "chunk_id":    r.get("chunk_id"),
                "doc_id":      r.get("document_id"),
                "text":        r.get("text", ""),
                "jurisdiction": r.get("jurisdiction", ""),
                "law_name":    r.get("law_name"),
                "article_no":  r.get("article_no"),
                "status":      r.get("status"),
                "score":       float(r.get("score", 0)),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[embedder] pgvector search failed ({e}), falling back to memory")
        return _search_memory(query_vec, jurisdiction, top_k)


# ── In-memory fallback (dev without Supabase) ─────────────────────────────────

def _store_in_memory(chunks: List[dict], embeddings) -> dict:
    with _lock:
        for chunk, emb in zip(chunks, embeddings):
            _mem_store[chunk.get("chunk_id", id(chunk))] = {
                "chunk_id":    chunk.get("chunk_id"),
                "doc_id":      chunk.get("doc_id"),
                "text":        chunk.get("text", ""),
                "jurisdiction": chunk.get("jurisdiction", ""),
                "law_name":    chunk.get("law_name"),
                "article_no":  chunk.get("article_no"),
                "status":      chunk.get("status", "ACTIVE"),
                "_embedding":  emb,
            }
    print(f"[embedder] in-memory: stored {len(chunks)} chunks (Supabase not configured)")
    return {"vectors_indexed": len(chunks), "model": f"{MODEL_NAME} (in-memory)"}


def _search_memory(query_vec, jurisdiction: str, top_k: int) -> List[dict]:
    """Cosine similarity search over the in-memory fallback store."""
    import numpy as np

    with _lock:
        items = list(_mem_store.values())

    if not items:
        return []

    query_np = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    results = []
    for item in items:
        if item.get("status", "ACTIVE") != "ACTIVE":
            continue
        if jurisdiction and item.get("jurisdiction") and item["jurisdiction"] != jurisdiction:
            continue
        emb = item["_embedding"]
        emb_norm = emb / (np.linalg.norm(emb) + 1e-10)
        score = float(np.dot(query_np, emb_norm))
        results.append({**{k: v for k, v in item.items() if k != "_embedding"}, "score": score})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


# ── Sentence-Transformers model singleton ─────────────────────────────────────

def _get_model():
    global _model
    if _model is not None:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        print(f"[embedder] Loading {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        print("[embedder] Model loaded")
        return _model
    except Exception as e:
        print(f"[embedder] sentence-transformers unavailable ({e})")
        return None
