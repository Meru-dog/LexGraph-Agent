"""report_formatter — generate structured reports from findings (LLM + Jinja2)."""

from datetime import date
from typing import List


def report_formatter(findings: list, template: str) -> dict:
    """Generate a structured report dict.

    Phase 2: deterministic template population.
    Phase 3: LLM narrative synthesis + Jinja2 HTML/DOCX rendering.
    """
    if template == "dd_report":
        return _build_dd_report(findings)
    if template == "contract_review":
        return _build_contract_report(findings)
    return {"template": template, "findings": findings}


def _build_dd_report(findings: list) -> dict:
    sections_map: dict[str, list] = {}
    for f in findings:
        sec = f.get("section", "08")
        sections_map.setdefault(sec, []).append({"status": f.get("status", "ok"), "text": f.get("text", "")})

    critical = sum(1 for f in findings if f.get("status") == "critical")
    high = sum(1 for f in findings if f.get("status") == "high")
    medium = sum(1 for f in findings if f.get("status") in ("medium", "warn"))
    low = sum(1 for f in findings if f.get("status") == "ok")

    return {
        "target": "Target Entity",
        "transaction": "Investment",
        "date": str(date.today()),
        "jurisdiction": "JP + US",
        "summary": {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "recommendation": "Review required before proceeding.",
        },
        "sections": [
            {"num": sec, "title": f"Section {sec}", "items": items}
            for sec, items in sorted(sections_map.items())
        ],
    }


def _build_contract_report(findings: list) -> dict:
    return {
        "clause_count": len(findings),
        "high_risk": [f for f in findings if f.get("status") in ("critical", "high")],
        "medium_risk": [f for f in findings if f.get("status") == "medium"],
        "generated_at": str(date.today()),
    }
