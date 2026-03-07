"""Append-only structured audit logger.

Writes one JSON line per event to ./data/audit.jsonl.
Suitable for dev; swap the handler for a DB writer in production.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "./data/audit.jsonl"))


def _log(event: str, actor: str, detail: dict[str, Any]) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        **detail,
    }
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Public helpers ────────────────────────────────────────────────────────────

def log_upload(actor: str, doc_id: str, filename: str) -> None:
    _log("upload", actor, {"doc_id": doc_id, "filename": filename})


def log_dd_start(actor: str, task_id: str, prompt: str) -> None:
    _log("dd_start", actor, {"task_id": task_id, "prompt": prompt[:120]})


def log_dd_approve(actor: str, task_id: str, approved: bool, notes: str) -> None:
    _log("dd_approve", actor, {"task_id": task_id, "approved": approved, "notes": notes[:200]})


def log_review_start(actor: str, task_id: str, doc_id: str) -> None:
    _log("review_start", actor, {"task_id": task_id, "doc_id": doc_id})


def log_export(actor: str, task_id: str, format: str) -> None:
    _log("export", actor, {"task_id": task_id, "format": format})


def log_login(actor: str, success: bool) -> None:
    _log("login", actor, {"success": success})
