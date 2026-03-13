"""Supabase Python client — database and auth admin operations.

Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY for server-side admin operations.
"""

import os
from functools import lru_cache

SUPABASE_URL = os.getenv("SUPABASE_URL", "") or os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")


@lru_cache(maxsize=1)
def get_supabase_client():
    """Return a cached Supabase admin client (uses service role key)."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as e:
        print(f"[supabase] Client init failed: {e}")
        return None


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


# ── Task storage (Supabase tables with in-memory fallback) ────────────────────

def upsert_task(table: str, task_id: str, data: dict) -> bool:
    """Insert or update a task in Supabase. Returns True on success."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table(table).upsert({"id": task_id, **data}).execute()
        return True
    except Exception as e:
        print(f"[supabase] upsert {table} failed: {e}")
        return False


def get_task(table: str, task_id: str) -> dict | None:
    """Fetch a single task from Supabase."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = client.table(table).select("*").eq("id", task_id).single().execute()
        return result.data
    except Exception:
        return None


def list_tasks(table: str, user_id: str | None = None, limit: int = 50) -> list[dict]:
    """List tasks from Supabase."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        q = client.table(table).select("*").order("created_at", desc=True).limit(limit)
        if user_id:
            q = q.eq("user_id", user_id)
        result = q.execute()
        return result.data or []
    except Exception:
        return []
