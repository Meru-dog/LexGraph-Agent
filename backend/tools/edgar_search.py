"""SEC EDGAR full-text search client — retrieves US financial disclosures.

Uses the public EDGAR full-text search API (no API key required).
  EFTS endpoint: https://efts.sec.gov/LATEST/search-index
  Submissions endpoint: https://data.sec.gov/submissions/CIK{cik:010d}.json

Supported filing types:
  10-K  = Annual report
  10-Q  = Quarterly report
  8-K   = Current report (material events)
  20-F  = Annual report for foreign private issuers
  6-K   = Report for foreign private issuers (current)
  S-1   = Registration statement (IPO)
  DEF 14A = Proxy statement
"""

import json
import re
import urllib.request
import urllib.parse
from typing import Optional


EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
EDGAR_BASE = "https://www.sec.gov"

_HEADERS = {
    "User-Agent": "LexGraphAgent research@lexgraph.ai",  # SEC requires User-Agent
    "Accept": "application/json",
}


def _get(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def search_filings(
    company_name: str,
    filing_types: Optional[list[str]] = None,
    max_results: int = 10,
    date_range_start: str = "",
    date_range_end: str = "",
) -> list[dict]:
    """Search SEC EDGAR for filings by company name.

    Args:
        company_name: Company or entity name (partial match)
        filing_types: List like ["10-K", "10-Q", "8-K"]; defaults to annual/quarterly/current
        max_results: Cap on returned items
        date_range_start: ISO date string "YYYY-MM-DD" (optional)
        date_range_end:   ISO date string "YYYY-MM-DD" (optional)

    Returns:
        List of filing dicts with keys:
          cik, entityName, filingType, filedAt, periodOfReport,
          accessionNo, edgar_url, description
    """
    if filing_types is None:
        filing_types = ["10-K", "10-Q", "8-K", "20-F"]

    results = []

    for ftype in filing_types:
        if len(results) >= max_results:
            break

        params: dict[str, str] = {
            "q": f'"{company_name}"',
            "dateRange": "custom" if date_range_start else "",
            "startdt": date_range_start,
            "enddt": date_range_end,
            "forms": ftype,
            "_source": "file_date,period_of_report,entity_name,file_num,form_type,accession_no,biz_location,inc_states",
        }
        # Remove empty params
        params = {k: v for k, v in params.items() if v}

        url = f"https://efts.sec.gov/LATEST/search-index?{urllib.parse.urlencode(params)}"
        data = _get(url)

        if "error" in data:
            # Fallback to EDGAR full-text search
            url2 = (
                f"https://efts.sec.gov/LATEST/search-index?q={urllib.parse.quote(company_name)}"
                f"&forms={ftype}"
            )
            data = _get(url2)

        hits = data.get("hits", {}).get("hits", [])
        for hit in hits[:max_results - len(results)]:
            src = hit.get("_source", {})
            acc = src.get("accession_no", "").replace("-", "")
            cik = str(src.get("file_num", "")).lstrip("0") or ""
            results.append({
                "cik": cik,
                "entityName": src.get("entity_name", company_name),
                "filingType": src.get("form_type", ftype),
                "filedAt": src.get("file_date", ""),
                "periodOfReport": src.get("period_of_report", ""),
                "accessionNo": src.get("accession_no", ""),
                "edgar_url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={urllib.parse.quote(company_name)}&type={ftype}&dateb=&owner=include&count=40",
                "description": f"{src.get('form_type', ftype)} filing",
            })

    return results


def search_company_cik(company_name: str) -> Optional[str]:
    """Look up a company's CIK number from EDGAR company search."""
    url = (
        f"https://efts.sec.gov/LATEST/search-index?"
        f"q={urllib.parse.quote(company_name)}&dateRange=custom&startdt=2020-01-01"
    )
    data = _get(url)
    hits = data.get("hits", {}).get("hits", [])
    if hits:
        src = hits[0].get("_source", {})
        # Try to extract entity_id / CIK
        entity_id = hits[0].get("_id", "")
        if entity_id:
            return entity_id.split(":")[0] if ":" in entity_id else None
    return None


def get_recent_filings(cik: str, max_results: int = 10) -> list[dict]:
    """Fetch recent filings for a known CIK via EDGAR submissions API."""
    cik_padded = cik.zfill(10)
    url = f"{SUBMISSIONS_BASE}/CIK{cik_padded}.json"
    data = _get(url)
    if "error" in data:
        return []

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    descriptions = filings.get("primaryDocument", [])
    periods = filings.get("reportDate", [])
    entity_name = data.get("name", "")

    results = []
    target_forms = {"10-K", "10-Q", "8-K", "20-F", "6-K", "S-1", "DEF 14A"}
    for i, form in enumerate(forms):
        if form in target_forms:
            acc = accessions[i] if i < len(accessions) else ""
            acc_path = acc.replace("-", "")
            results.append({
                "cik": cik,
                "entityName": entity_name,
                "filingType": form,
                "filedAt": dates[i] if i < len(dates) else "",
                "periodOfReport": periods[i] if i < len(periods) else "",
                "accessionNo": acc,
                "edgar_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_path}/",
                "description": descriptions[i] if i < len(descriptions) else "",
            })
            if len(results) >= max_results:
                break
    return results


def fetch_filing_text(edgar_url: str, max_chars: int = 8000) -> str:
    """Attempt to fetch plain text from an EDGAR filing index URL."""
    req = urllib.request.Request(edgar_url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", raw)
            text = re.sub(r"&[a-z]+;", " ", text)
            text = re.sub(r"\s{2,}", " ", text).strip()
            return text[:max_chars]
    except Exception as e:
        return f"[Filing text unavailable: {e}]"
