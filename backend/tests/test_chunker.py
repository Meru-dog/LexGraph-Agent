"""Tests for ingestion.chunker — statute-aware structural chunking."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingestion.chunker import (
    chunk_text,
    _looks_jp,
    _extract_jp_article_no,
    _extract_us_section_no,
    _extract_contract_article_no,
    _split_by_pattern,
    _JP_ARTICLE,
    _US_SECTION,
    _CONTRACT_CLAUSE,
    CHUNK_SIZE,
    MAX_CHUNK_CHARS,
    OVERLAP_CHARS,
)


# ── Empty / trivial inputs ───────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_text(self):
        assert chunk_text("", "doc1") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n  \t  ", "doc1") == []

    def test_short_text_fallback(self):
        chunks = chunk_text("Hello world.", "doc1")
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Hello world."
        assert chunks[0]["doc_id"] == "doc1"


# ── Chunk metadata ───────────────────────────────────────────────────────────


class TestChunkMetadata:
    def test_chunk_has_required_fields(self):
        chunks = chunk_text("Some text here.", "doc1", law_name="Test Law", jurisdiction="JP")
        c = chunks[0]
        assert "chunk_id" in c
        assert c["doc_id"] == "doc1"
        assert c["law_name"] == "Test Law"
        assert c["jurisdiction"] == "JP"
        assert c["chunk_index"] == 0
        assert "token_count_approx" in c

    def test_token_count_approx(self):
        text = "a" * 400  # 400 chars ≈ 100 tokens
        chunks = chunk_text(text, "doc1")
        assert chunks[0]["token_count_approx"] == 100


# ── JP statute chunking ─────────────────────────────────────────────────────


class TestJPStatute:
    def test_splits_at_article_boundaries(self):
        text = "第1条 この法律は会社法という。\n第2条 定義は次のとおり。\n第3条 法人格を有する。"
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="JP")
        assert len(chunks) == 3

    def test_article_no_extracted(self):
        text = "第1条 この法律は会社法という。\n第2条 定義は次のとおり。"
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="JP")
        articles = [c["article_no"] for c in chunks]
        assert "1条" in articles[0] or "1" in articles[0]

    def test_jurisdiction_set(self):
        text = "第1条 テスト。\n第2条 テスト。"
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="JP")
        assert all(c["jurisdiction"] == "JP" for c in chunks)

    def test_auto_detect_jp(self):
        text = "第1条 この法律は会社法という。\n第2条 定義は次のとおり。"
        chunks = chunk_text(text, "doc1", document_type="statute")
        assert len(chunks) >= 2

    def test_single_article_fallback(self):
        text = "第1条 この法律は短い。"
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="JP")
        assert len(chunks) >= 1


# ── US statute chunking ─────────────────────────────────────────────────────


class TestUSStatute:
    def test_splits_at_section_boundaries(self):
        text = "Section 1. Short title.\nSection 2. Definitions.\nSection 3. Application."
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="US")
        assert len(chunks) == 3

    def test_section_number_extracted(self):
        text = "Section 10. Registration.\nSection 11. Information."
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="US")
        assert any("10" in c["article_no"] for c in chunks)

    def test_paragraph_symbol(self):
        text = "§ 302 Requirements.\n§ 303 Compliance."
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="US")
        assert len(chunks) == 2

    def test_jurisdiction_set_us(self):
        text = "Section 1. Test.\nSection 2. Test."
        chunks = chunk_text(text, "doc1", document_type="statute", jurisdiction="US")
        assert all(c["jurisdiction"] == "US" for c in chunks)


# ── Contract chunking ───────────────────────────────────────────────────────


class TestContract:
    def test_splits_at_article_heading(self):
        text = "Article 1 Definitions\nThe following terms apply.\nArticle 2 Payment\nPayment shall be made."
        chunks = chunk_text(text, "doc1", document_type="contract")
        assert len(chunks) == 2

    def test_clause_heading(self):
        text = "CLAUSE 1 Scope of Work\nContractor shall perform.\nCLAUSE 2 Compensation\nPayment is due."
        chunks = chunk_text(text, "doc1", document_type="contract")
        assert len(chunks) == 2

    def test_jp_contract(self):
        text = "第1条 目的\nこの契約は業務委託について定める。\n第2条 報酬\n報酬は月額100万円とする。"
        chunks = chunk_text(text, "doc1", document_type="contract", jurisdiction="JP")
        assert len(chunks) == 2


# ── Fixed-size fallback ──────────────────────────────────────────────────────


class TestFixedChunking:
    def test_long_text_splits(self):
        text = "word " * 1000  # 5000 chars > MAX_CHUNK_CHARS
        chunks = chunk_text(text, "doc1")
        assert len(chunks) > 1

    def test_overlap_exists(self):
        text = "x" * (MAX_CHUNK_CHARS * 2)
        chunks = chunk_text(text, "doc1")
        assert len(chunks) >= 2
        # Chunks should overlap
        total_chars = sum(len(c["text"]) for c in chunks)
        assert total_chars > len(text.strip())

    def test_chunk_index_sequential(self):
        text = "word " * 1000
        chunks = chunk_text(text, "doc1")
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks)))


# ── Helper functions ─────────────────────────────────────────────────────────


class TestHelpers:
    def test_looks_jp_hiragana(self):
        assert _looks_jp("これはテストです")

    def test_looks_jp_kanji(self):
        assert _looks_jp("会社法第一条")

    def test_looks_jp_false(self):
        assert not _looks_jp("This is English text only")

    def test_extract_jp_article_no(self):
        assert _extract_jp_article_no("第330条の2 取締役の義務") == "330条の2"

    def test_extract_jp_article_no_empty(self):
        assert _extract_jp_article_no("Some random text") == ""

    def test_extract_us_section_no(self):
        assert _extract_us_section_no("Section 10.5 Registration") == "10.5"

    def test_extract_us_section_no_empty(self):
        assert _extract_us_section_no("Some random text") == ""

    def test_extract_contract_article_no(self):
        assert _extract_contract_article_no("Article 5 Payment") == "5"

    def test_extract_contract_article_no_clause(self):
        assert _extract_contract_article_no("CLAUSE 3 Termination") == "3"

    def test_split_by_pattern_no_match(self):
        result = _split_by_pattern(_JP_ARTICLE, "No articles here")
        assert result == ["No articles here"]

    def test_split_by_pattern_jp(self):
        text = "第1条 テスト。第2条 テスト。"
        result = _split_by_pattern(_JP_ARTICLE, text)
        assert len(result) == 2


# ── Document type routing ────────────────────────────────────────────────────


class TestDocumentTypeRouting:
    def test_regulation_uses_statute_strategy(self):
        text = "Section 1. Rule.\nSection 2. Enforcement."
        chunks = chunk_text(text, "doc1", document_type="regulation", jurisdiction="US")
        assert len(chunks) == 2

    def test_case_law_type(self):
        text = "FACTS: The defendant filed a motion.\nHELD: The motion was denied."
        chunks = chunk_text(text, "doc1", document_type="case_law", jurisdiction="US")
        assert len(chunks) >= 2

    def test_other_type_fallback(self):
        text = "Some memo content."
        chunks = chunk_text(text, "doc1", document_type="other")
        assert len(chunks) == 1
