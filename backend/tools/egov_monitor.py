"""e-Gov amendment monitor — checks for updated law versions via e-Gov API (RDD §10.3, Phase 6).

e-Gov API v3: https://laws.e-gov.go.jp/api/1/lawdata/{law_id}
Returns current law text + revision history.

Usage:
    from tools.egov_monitor import check_amendments
    result = check_amendments(law_ids=["325AC0000000086"])  # 会社法

Env vars:
    EGOV_API_KEY — optional; improves rate limits (e-Gov v3 may not require a key)
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import date, datetime, timezone
from typing import Optional

EGOV_BASE_URL = "https://laws.e-gov.go.jp/api/1"
EGOV_API_KEY = os.getenv("EGOV_API_KEY", "")

# Well-known JP law IDs (asahi_id format used by e-Gov)
TRACKED_LAWS: dict[str, str] = {
    "325AC0000000086": "会社法",
    "345AC0000000025": "金融商品取引法",
    "129AC0000000089": "民法",
    "348AC0000000054": "独占禁止法",
    "322AC0000000049": "労働基準法",
    "349AC0000000001": "独占禁止法施行令",
}


def _egov_request(path: str) -> dict:
    """Make a request to the e-Gov law API. Returns parsed JSON."""
    url = f"{EGOV_BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    if EGOV_API_KEY:
        headers["Authorization"] = f"Bearer {EGOV_API_KEY}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def get_law_info(law_id: str) -> dict:
    """Fetch metadata for a single law from e-Gov.

    Returns a dict with law_id, law_name, promulgation_date, last_amendment_date.
    Raises on network error.
    """
    try:
        data = _egov_request(f"/lawdata/{law_id}")
        law_data = data.get("law_data", {}) or data
        return {
            "law_id": law_id,
            "law_name": law_data.get("law_full_name") or law_data.get("law_name", ""),
            "promulgation_date": law_data.get("promulgation_date", ""),
            "last_amendment_date": law_data.get("last_amendment_date", ""),
            "revision_count": len(law_data.get("revision_history", [])),
        }
    except Exception as e:
        return {"law_id": law_id, "error": str(e)}


def check_amendments(
    law_ids: Optional[list[str]] = None,
    since_date: Optional[str] = None,
) -> dict:
    """Check for law amendments since a given date.

    Args:
        law_ids:    List of e-Gov law IDs to check. Defaults to TRACKED_LAWS.
        since_date: ISO date string (e.g. "2025-01-01"). Defaults to 90 days ago.

    Returns:
        {
            "checked_at": ISO timestamp,
            "since_date": date string,
            "results": [
                {
                    "law_id": ...,
                    "law_name": ...,
                    "last_amendment_date": ...,
                    "is_amended": bool,   # True if amended since since_date
                    "error": str | None,
                }
            ],
            "amended_count": int,
            "error_count": int,
        }
    """
    ids = law_ids or list(TRACKED_LAWS.keys())
    if since_date is None:
        from datetime import timedelta
        since_date = (date.today() - timedelta(days=90)).isoformat()

    results = []
    amended_count = 0
    error_count = 0

    for law_id in ids:
        time.sleep(0.3)  # Respect e-Gov rate limits (~3 req/s)
        info = get_law_info(law_id)
        if "error" in info:
            error_count += 1
            results.append({
                "law_id": law_id,
                "law_name": TRACKED_LAWS.get(law_id, law_id),
                "last_amendment_date": None,
                "is_amended": False,
                "error": info["error"],
            })
            continue

        last_amended = info.get("last_amendment_date") or ""
        is_amended = bool(last_amended and last_amended >= since_date)
        if is_amended:
            amended_count += 1

        results.append({
            "law_id": law_id,
            "law_name": info.get("law_name") or TRACKED_LAWS.get(law_id, law_id),
            "last_amendment_date": last_amended,
            "is_amended": is_amended,
            "error": None,
        })

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "since_date": since_date,
        "results": results,
        "amended_count": amended_count,
        "error_count": error_count,
        "total_checked": len(ids),
    }


def archive_amended_nodes(amendment_results: dict) -> dict:
    """For each amended law, archive its Neo4j node and record AMENDED_BY edge.

    Should be run after `check_amendments()` when is_amended=True.
    Non-fatal: logs errors but does not raise.
    """
    archived = []
    errors = []

    amended = [r for r in amendment_results.get("results", []) if r.get("is_amended")]
    if not amended:
        return {"archived": [], "errors": [], "message": "No amendments to process"}

    try:
        from graph.neo4j_client import neo4j_client
        from graph.metadata import AmendmentManager
        if not neo4j_client._driver:
            return {"archived": [], "errors": ["Neo4j not connected"], "message": "skipped"}
        mgr = AmendmentManager(neo4j_client)
    except Exception as e:
        return {"archived": [], "errors": [str(e)], "message": "Neo4j unavailable"}

    for result in amended:
        law_id = result["law_id"]
        amended_date = result.get("last_amendment_date") or date.today().isoformat()
        try:
            # Find ACTIVE nodes for this law
            with neo4j_client._driver.session() as session:
                rows = list(session.run(
                    "MATCH (n) WHERE n.law_id = $lid AND (n.status IS NULL OR n.status = 'ACTIVE') "
                    "RETURN n.node_id AS nid",
                    {"lid": law_id},
                ))
            for row in rows:
                nid = row["nid"]
                if nid:
                    mgr.amend_node(nid, f"{nid}_v_amended", {}, amended_date)
                    archived.append(nid)
        except Exception as e:
            errors.append(f"{law_id}: {e}")

    return {
        "archived": archived,
        "errors": errors,
        "amended_laws": [r["law_name"] for r in amended],
    }
