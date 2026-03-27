"""Tests for tools.report_formatter — DD and contract report generation."""

import pytest
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.report_formatter import (
    report_formatter,
    _build_dd_report,
    _build_contract_report,
    _DD_SECTION_TITLES,
)


# ── report_formatter dispatch ────────────────────────────────────────────────


class TestReportFormatter:
    def test_dd_template(self):
        result = report_formatter([], "dd_report")
        assert "sections" in result
        assert "summary" in result

    def test_contract_template(self):
        result = report_formatter([], "contract_review")
        assert "clause_count" in result

    def test_unknown_template(self):
        result = report_formatter([{"x": 1}], "other_template")
        assert result["template"] == "other_template"
        assert result["findings"] == [{"x": 1}]


# ── DD report ────────────────────────────────────────────────────────────────


class TestDDReport:
    def test_empty_findings(self):
        report = _build_dd_report([])
        assert len(report["sections"]) == 12
        assert report["summary"]["critical"] == 0
        assert report["summary"]["high"] == 0

    def test_all_sections_present(self):
        report = _build_dd_report([])
        section_nums = [s["num"] for s in report["sections"]]
        for num in _DD_SECTION_TITLES:
            assert num in section_nums

    def test_sections_sorted(self):
        report = _build_dd_report([])
        nums = [s["num"] for s in report["sections"]]
        assert nums == sorted(nums)

    def test_findings_categorized(self):
        findings = [
            {"section": "01", "status": "critical", "text": "Missing board minutes"},
            {"section": "01", "status": "ok", "text": "Governance structure exists"},
            {"section": "08", "status": "high", "text": "Pending lawsuit"},
        ]
        report = _build_dd_report(findings)
        assert report["summary"]["critical"] == 1
        assert report["summary"]["high"] == 1
        assert report["summary"]["low"] == 1

    def test_section_title_populated(self):
        report = _build_dd_report([])
        for section in report["sections"]:
            assert section["title"] == _DD_SECTION_TITLES[section["num"]]

    def test_date_is_today(self):
        report = _build_dd_report([])
        assert report["date"] == str(date.today())

    def test_medium_warn_counted(self):
        findings = [
            {"status": "medium", "text": "test"},
            {"status": "warn", "text": "test"},
        ]
        report = _build_dd_report(findings)
        assert report["summary"]["medium"] == 2

    def test_default_section_08(self):
        findings = [{"status": "ok", "text": "test"}]
        report = _build_dd_report(findings)
        sec_08 = [s for s in report["sections"] if s["num"] == "08"][0]
        assert len(sec_08["items"]) == 1


# ── Contract report ──────────────────────────────────────────────────────────


class TestContractReport:
    def test_empty(self):
        report = _build_contract_report([])
        assert report["clause_count"] == 0
        assert report["high_risk"] == []
        assert report["medium_risk"] == []

    def test_risk_classification(self):
        findings = [
            {"status": "critical", "text": "Unlimited liability"},
            {"status": "high", "text": "No IP assignment"},
            {"status": "medium", "text": "30-day notice period"},
            {"status": "ok", "text": "Standard governing law"},
        ]
        report = _build_contract_report(findings)
        assert report["clause_count"] == 4
        assert len(report["high_risk"]) == 2  # critical + high
        assert len(report["medium_risk"]) == 1

    def test_generated_at(self):
        report = _build_contract_report([])
        assert report["generated_at"] == str(date.today())
