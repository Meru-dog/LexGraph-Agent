"""embedder — multilingual-e5-large embedding generation and FAISS indexing.

Uses a singleton SentenceTransformer + FAISS IndexFlatIP (inner-product after L2-norm
≡ cosine similarity). The index is persisted to FAISS_INDEX_PATH on each update.
"""

import os
import threading
from pathlib import Path
from typing import List

FAISS_INDEX_PATH = Path(os.getenv("FAISS_INDEX_PATH", "./data/faiss.index"))
FAISS_META_PATH = Path(os.getenv("FAISS_INDEX_PATH", "./data/faiss.index")).with_suffix(".meta.json")
MODEL_NAME = "intfloat/multilingual-e5-large"
VECTOR_DIM = 1024  # multilingual-e5-large output dimension

_model = None
_faiss_index = None
_chunk_meta: dict = {}      # chunk_id → {doc_id, text, ...}
_lock = threading.Lock()


def embed_chunks(chunks: List[dict]) -> dict:
    """Embed chunks with multilingual-e5-large and add to FAISS index.

    Falls back to stub behaviour (returns count) if sentence-transformers or
    faiss-cpu are not installed.
    """
    if not chunks:
        return {"vectors_indexed": 0, "model": MODEL_NAME}

    model = _get_model()
    index = _get_index()
    if model is None or index is None:
        return {"vectors_indexed": len(chunks), "model": f"{MODEL_NAME} (stub)"}

    import numpy as np

    texts = [f"passage: {c['text']}" for c in chunks]
    # num_workers=0 avoids forking a multiprocessing.resource_tracker child process,
    # which deadlocks when the parent is inside an asyncio event loop on macOS.
    embeddings = model.encode(
        texts, batch_size=32, normalize_embeddings=True,
        show_progress_bar=False, num_workers=0,
    )
    vectors = np.array(embeddings, dtype=np.float32)

    with _lock:
        # FAISS uses int64 IDs; map chunk_id string → sequential int
        start_id = index.ntotal
        ids = np.arange(start_id, start_id + len(chunks), dtype=np.int64)
        index.add_with_ids(vectors, ids)
        for i, chunk in enumerate(chunks):
            _chunk_meta[int(ids[i])] = {
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "text": chunk.get("text", ""),
                "jurisdiction": chunk.get("jurisdiction", ""),
            }
        _persist_index(index)

    return {"vectors_indexed": len(chunks), "model": MODEL_NAME}


def search_chunks(query: str, jurisdiction: str, top_k: int = 5) -> List[dict]:
    """Query the FAISS index and return the top-k most similar chunks."""
    model = _get_model()
    index = _get_index()
    if model is None or index is None or index.ntotal == 0:
        return []

    import numpy as np

    query_vec = model.encode([f"query: {query}"], normalize_embeddings=True, show_progress_bar=False)
    query_np = np.array(query_vec, dtype=np.float32)

    distances, ids = index.search(query_np, top_k)
    results = []
    for dist, idx in zip(distances[0], ids[0]):
        if idx < 0:
            continue
        meta = _chunk_meta.get(int(idx), {})
        # If jurisdiction filter is set, skip non-matching chunks
        if jurisdiction and meta.get("jurisdiction") and meta["jurisdiction"] != jurisdiction:
            continue
        results.append({**meta, "score": float(dist)})
    return results


# ─── Singletons ───────────────────────────────────────────────────────────────

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
        print(f"[embedder] sentence-transformers not available ({e})")
        return None


def _get_index():
    global _faiss_index, _chunk_meta
    if _faiss_index is not None:
        return _faiss_index
    try:
        import faiss, json
        if FAISS_INDEX_PATH.exists():
            try:
                _faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
                if FAISS_META_PATH.exists():
                    with open(FAISS_META_PATH) as f:
                        _chunk_meta = {int(k): v for k, v in json.load(f).items()}
                print(f"[embedder] FAISS index loaded ({_faiss_index.ntotal} vectors)")
            except Exception as load_err:
                print(f"[embedder] Corrupt FAISS index removed ({load_err}); creating fresh")
                FAISS_INDEX_PATH.unlink(missing_ok=True)
                FAISS_META_PATH.unlink(missing_ok=True)
                _chunk_meta = {}
                _faiss_index = faiss.IndexIDMap(faiss.IndexFlatIP(VECTOR_DIM))
        else:
            _faiss_index = faiss.IndexIDMap(faiss.IndexFlatIP(VECTOR_DIM))
            print("[embedder] FAISS index created (new)")
        return _faiss_index
    except Exception as e:
        print(f"[embedder] faiss-cpu not available ({e})")
        return None


def _persist_index(index) -> None:
    try:
        import faiss, json
        FAISS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(FAISS_INDEX_PATH))
        with open(FAISS_META_PATH, "w") as f:
            json.dump({str(k): v for k, v in _chunk_meta.items()}, f)
    except Exception as e:
        print(f"[embedder] FAISS persist error: {e}")
