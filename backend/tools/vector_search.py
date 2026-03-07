"""vector_search — semantic chunk retrieval via the FAISS index."""

from typing import List


def vector_search(query: str, jurisdiction: str, top_k: int = 5) -> List[dict]:
    """Retrieve top-k semantically similar chunks from the FAISS index.

    Delegates to ingestion.embedder.search_chunks which owns the singleton index.
    Returns an empty list if the index is empty or models aren't loaded yet.
    """
    try:
        from ingestion.embedder import search_chunks
        return search_chunks(query, jurisdiction, top_k)
    except Exception as e:
        print(f"[vector_search] error: {e}")
        return []
