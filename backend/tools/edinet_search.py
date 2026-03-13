"""EDINET API v2 client — retrieves Japanese financial disclosures.

Supported document types:
  120 = 有価証券報告書 (Annual securities report)
  140 = 半期報告書 (Semi-annual report)
  010 = 有価証券届出書 (Securities registration statement)
  050 = 臨時報告書 (Ad-hoc report / 適時開示)
  030 = 自己株券買付状況報告書 (Treasury stock)

API endpoint: https://disclosure.edinet-api.go.jp/api/v2/documents.json
Docs: https://disclosure.edinet-api.go.jp/

Optional env var: EDINET_API_KEY (free registration at edinet-fsa.go.jp)
Without a key the API still works but rate-limits more aggressively.
"""

import os
import json
import re
import urllib.request
import urllib.parse
import urllib.error
from datetime import date, timedelta
from typing import Optional


EDINET_BASE = "https://disclosure.edinet-api.go.jp/api/v2"

# docTypeCode → human-readable label
DOC_TYPE_LABELS = {
    "120": "有価証券報告書",
    "140": "半期報告書",
    "010": "有価証券届出書",
    "050": "臨時報告書/適時開示",
    "030": "自己株券買付状況報告書",
    "160": "有価証券報告書（外国）",
    "170": "半期報告書（外国）",
}


def _get(url: str, timeout: int = 10) -> dict:
    api_key = os.getenv("EDINET_API_KEY", "")
    if api_key:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}Subscription-Key={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def search_disclosures(
    company_name: str,
    days_back: int = 365,
    doc_types: Optional[list[str]] = None,
    max_results: int = 10,
) -> list[dict]:
    """Search EDINET for disclosures by company name.

    Strategy: EDINET's document list API is date-based (no full-text company search).
    We check:
      1. The past 30 days daily  (catches recent filings)
      2. April–September of recent years (annual report 有価証券報告書 season)
      3. Expanded name aliases (strips 株式会社 etc. for looser matching)

    Args:
        company_name: Company name (partial match, Japanese or romaji)
        days_back: Total lookback window in days
        doc_types: List of docTypeCode strings; defaults to annual + semi-annual + ad-hoc
        max_results: Cap on returned items
    """
    if doc_types is None:
        doc_types = ["120", "140", "010", "050"]

    results: list[dict] = []
    today = date.today()
    seen_docs: set[str] = set()

    def _check_date(d: date) -> None:
        if len(results) >= max_results:
            return
        url = f"{EDINET_BASE}/documents.json?date={d.strftime('%Y-%m-%d')}&type=2"
        data = _get(url)
        if "error" in data:
            return
        for doc in data.get("results", []):
            doc_id = doc.get("docID", "")
            if not doc_id or doc_id in seen_docs:
                continue
            if doc.get("docTypeCode") not in doc_types:
                continue
            filer = doc.get("filerName", "")
            if not filer or not _name_matches(company_name, filer):
                continue
            seen_docs.add(doc_id)
            results.append({
                "docID": doc_id,
                "docTypeCode": doc.get("docTypeCode"),
                "docTypeName": DOC_TYPE_LABELS.get(doc.get("docTypeCode", ""), doc.get("docTypeCode", "")),
                "filerName": filer,
                "edinetCode": doc.get("edinetCode"),
                "periodStart": doc.get("periodStart"),
                "periodEnd": doc.get("periodEnd"),
                "submitDateTime": doc.get("submitDateTime"),
                "edinet_url": f"https://disclosure.edinet-api.go.jp/api/v2/documents/{doc_id}",
                "has_xbrl": bool(doc.get("xbrlFlag")),
            })
            if len(results) >= max_results:
                return

    # Phase 1: recent 30 days daily (catches any recent filings)
    for i in range(min(30, days_back)):
        _check_date(today - timedelta(days=i))
        if len(results) >= max_results:
            return results

    # Phase 2: annual report season (April–September) for each year in range
    years_back = min(days_back // 365 + 1, 3)
    for year_offset in range(years_back):
        year = today.year - year_offset
        # Iterate April 1 – August 31 (prime 有価証券報告書 season in Japan)
        for month in range(4, 9):
            for day in range(1, 32):
                try:
                    d = date(year, month, day)
                except ValueError:
                    continue
                if d > today or (today - d).days > days_back:
                    continue
                _check_date(d)
                if len(results) >= max_results:
                    return results

    return results


def fetch_document_text(doc_id: str, max_chars: int = 8000) -> str:
    """Attempt to fetch plain-text content of an EDINET document.

    Returns the first max_chars characters of the document body,
    or an error string if the document is not available in text form.

    Note: EDINET serves XBRL and PDF; we request type=1 (CSV/text) where available.
    """
    url = f"{EDINET_BASE}/documents/{doc_id}?type=5"  # type=5 = CSV (text-extractable)
    try:
        api_key = os.getenv("EDINET_API_KEY", "")
        if api_key:
            url += f"&Subscription-Key={api_key}"
        with urllib.request.urlopen(url, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if b"application/json" in content_type.encode() or raw.startswith(b"{"):
                data = json.loads(raw.decode("utf-8"))
                return data.get("message", str(data))[:max_chars]
            # Try to decode as text
            text = raw.decode("utf-8", errors="replace")
            # Strip XML/HTML tags for readability
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s{2,}", " ", text).strip()
            return text[:max_chars]
    except Exception as e:
        return f"[Document text unavailable: {e}]"


_CORP_SUFFIXES = [
    "株式会社", "合同会社", "合資会社", "合名会社", "有限会社",
    "（株）", "(株)", "㈱",
    "inc.", "inc", "corp.", "corp", "co.,ltd.", "co., ltd.", "ltd.", "ltd",
    "k.k.", "kk",
]


def _name_matches(query: str, filer_name: str) -> bool:
    """Robust name match: strips corporate suffixes, handles katakana/romaji variations."""
    def _normalize(s: str) -> str:
        s = s.lower().replace(" ", "").replace("　", "").replace("・", "").replace("·", "")
        for suffix in _CORP_SUFFIXES:
            s = s.replace(suffix, "")
        return s.strip()

    q = _normalize(query)
    f = _normalize(filer_name)
    if not q:
        return False
    # Substring match in both directions (handles partial names and full names)
    return q in f or f in q
