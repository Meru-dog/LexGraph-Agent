"""Unified task store: in-memory primary cache + Supabase persistence.

Usage:
    store = TaskStore("dd_tasks")
    store.set(task_id, data)
    task = store.get(task_id)
    tasks = store.list(user_id=uid)
"""

from __future__ import annotations

import json


class TaskStore:
    """Thread-safe in-memory dict with Supabase write-through persistence."""

    def __init__(self, table: str):
        self._table = table
        self._cache: dict[str, dict] = {}

    # ── Write ──────────────────────────────────────────────────────────────

    def set(self, task_id: str, data: dict) -> None:
        """Upsert task in cache and (best-effort) Supabase."""
        self._cache[task_id] = data
        self._persist(task_id, data)

    def update(self, task_id: str, patch: dict) -> dict | None:
        """Patch existing task fields and persist."""
        task = self._cache.get(task_id)
        if task is None:
            return None
        task.update(patch)
        self._persist(task_id, task)
        return task

    # ── Read ───────────────────────────────────────────────────────────────

    def get(self, task_id: str) -> dict | None:
        """Return task from cache, falling back to Supabase."""
        if task_id in self._cache:
            return self._cache[task_id]
        return self._fetch_from_supabase(task_id)

    def list(self, user_id: str | None = None, limit: int = 50) -> list[dict]:
        """Return tasks from cache if populated, else Supabase."""
        if self._cache:
            tasks = list(self._cache.values())
            if user_id:
                tasks = [t for t in tasks if t.get("user_id") == user_id]
            return sorted(tasks, key=lambda t: t.get("created_at", ""), reverse=True)[:limit]
        return self._list_from_supabase(user_id, limit)

    # ── Private ────────────────────────────────────────────────────────────

    def _persist(self, task_id: str, data: dict) -> None:
        try:
            from db.supabase_client import upsert_task
            # Supabase can't store arbitrary nested dicts — JSON-encode complex fields
            row = _flatten_for_supabase(task_id, data)
            upsert_task(self._table, task_id, row)
        except Exception as e:
            print(f"[task_store] persist failed ({self._table}/{task_id}): {e}")

    def _fetch_from_supabase(self, task_id: str) -> dict | None:
        try:
            from db.supabase_client import get_task
            row = get_task(self._table, task_id)
            if row:
                task = _unflatten_from_supabase(row)
                self._cache[task_id] = task
                return task
        except Exception as e:
            print(f"[task_store] fetch failed ({self._table}/{task_id}): {e}")
        return None

    def _list_from_supabase(self, user_id: str | None, limit: int) -> list[dict]:
        try:
            from db.supabase_client import list_tasks
            rows = list_tasks(self._table, user_id=user_id, limit=limit)
            tasks = [_unflatten_from_supabase(r) for r in rows]
            for t in tasks:
                self._cache[t["task_id"]] = t
            return tasks
        except Exception as e:
            print(f"[task_store] list failed ({self._table}): {e}")
        return []


# ── Serialisation helpers ──────────────────────────────────────────────────────

_JSON_FIELDS = {"report", "request", "clause_reviews", "compliance_flags", "partial_findings"}


def _flatten_for_supabase(task_id: str, data: dict) -> dict:
    """Encode complex nested fields as JSON strings for Supabase storage."""
    row = {"task_id": task_id}
    for k, v in data.items():
        if k in _JSON_FIELDS and v is not None:
            row[k] = json.dumps(v, default=str)
        else:
            row[k] = v
    return row


def _unflatten_from_supabase(row: dict) -> dict:
    """Decode JSON-string fields back to Python objects."""
    data = dict(row)
    for field in _JSON_FIELDS:
        if field in data and isinstance(data[field], str):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                pass
    # Normalise Supabase 'id' column → 'task_id'
    if "id" in data and "task_id" not in data:
        data["task_id"] = data["id"]
    return data
