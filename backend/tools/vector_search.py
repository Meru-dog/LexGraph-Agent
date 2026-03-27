"""vector_search — semantic chunk retrieval via Supabase pgvector.

Delegates to ingestion.embedder.search_chunks which owns the embedding model
and the pgvector / in-memory store. Filters ARCHIVED chunks by default so that
repealed or superseded statutes are never returned in search results.
"""

from typing import List


def vector_search(
    query: str,
    jurisdiction: str,
    top_k: int = 5,
    status: str = "ACTIVE",
) -> List[dict]:
    """Retrieve top-k semantically similar chunks.

    Args:
        query:        Natural language query.
        jurisdiction: "JP" | "US" | "" (empty = no filter).
        top_k:        Number of results to return.
        status:       "ACTIVE" (default) excludes ARCHIVED/repealed chunks.

    Returns:
        List of chunk dicts with keys: chunk_id, doc_id, text, jurisdiction,
        law_name, article_no, status, score.
    """
    try:
        from ingestion.embedder import search_chunks
        return search_chunks(query, jurisdiction, top_k, status)
    except Exception as e:
        print(f"[vector_search] error: {e}")
        return []
