"""chunker — statute-aware structural chunking (RDD §7.4).

Strategy:
  JP statute  → split at 条/項/号 boundaries (regex)
  US statute  → split at Section / § / (a)(b) boundaries
  Contract    → split at article / clause headings
  Plain text  → fixed 512-token overlapping windows (fallback)

Each chunk carries law_name, article_no, section, jurisdiction metadata
so downstream retrieval can cite precisely.
"""

import re
import uuid
from typing import List, Optional

# ─── Constants ────────────────────────────────────────────────────────────────

CHUNK_SIZE = 512          # tokens (approx: 1 token ≈ 4 chars)
CHUNK_OVERLAP = 64
MAX_CHUNK_CHARS = CHUNK_SIZE * 4
OVERLAP_CHARS = CHUNK_OVERLAP * 4

# ─── JP statute patterns ──────────────────────────────────────────────────────
# Matches: 「第1条」「第一条」「第１条」「第1条の2」
_JP_ARTICLE = re.compile(
    r"(?=第[0-9０-９一二三四五六七八九十百千]+条(?:の[0-9０-９一二三四五六七八九十]+)?)"
)

# ─── US statute patterns ──────────────────────────────────────────────────────
# Matches: "Section 10.", "Sec. 5", "§ 302", "(a)", "(b)(1)"
_US_SECTION = re.compile(
    r"(?=(?:Section|Sec\.|§)\s*\d[\d.]*|^\s*\([a-z]\))", re.MULTILINE
)

# ─── Contract clause patterns ─────────────────────────────────────────────────
# Matches: "Article 1.", "第1条", "CLAUSE 3", "1. Payment"
_CONTRACT_CLAUSE = re.compile(
    r"(?=(?:Article|ARTICLE|Clause|CLAUSE)\s+\d|第[0-9０-９]+条|\d+\.\s+[A-Z\u3040-\u9FFF])"
)


# ─── Public API ───────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    doc_id: str,
    document_type: str = "other",
    jurisdiction: str = "",
    law_name: str = "",
) -> List[dict]:
    """Split text into chunks using the appropriate strategy.

    Args:
        text:          Raw extracted text.
        doc_id:        Parent document ID.
        document_type: "statute" | "case_law" | "contract" | "regulation" | "other"
        jurisdiction:  "JP" | "US" | ""
        law_name:      Statute title (for metadata on each chunk).

    Returns:
        List of chunk dicts with chunk_id, text, article_no, position, etc.
    """
    if not text.strip():
        return []

    dtype = document_type.lower().replace(" ", "_").replace("-", "_")

    if dtype in ("statute", "regulation"):
        if jurisdiction == "JP" or _looks_jp(text):
            return _chunk_jp_statute(text, doc_id, law_name)
        return _chunk_us_statute(text, doc_id, law_name)

    if dtype == "case_law":
        return _chunk_case(text, doc_id, law_name, jurisdiction)

    if dtype == "contract":
        return _chunk_contract(text, doc_id, law_name, jurisdiction)

    # Default: overlapping fixed-size windows
    return _chunk_fixed(text, doc_id, law_name, jurisdiction)


# ─── JP statute chunker ───────────────────────────────────────────────────────

def _chunk_jp_statute(text: str, doc_id: str, law_name: str) -> List[dict]:
    """Split at 条 boundaries; sub-split long 条 at 項 level."""
    segments = _split_by_pattern(_JP_ARTICLE, text)
    if len(segments) <= 1:
        return _chunk_fixed(text, doc_id, law_name, "JP")

    chunks = []
    chunk_index = 0
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        article_no = _extract_jp_article_no(seg)
        # Sub-split oversized 条 at 項 level
        if len(seg) > MAX_CHUNK_CHARS:
            sub_segs = _split_at_jp_paragraph(seg)
            for i, sub in enumerate(sub_segs):
                sub = sub.strip()
                if not sub:
                    continue
                chunks.append(_make_chunk(
                    text=sub, doc_id=doc_id, chunk_index=chunk_index,
                    article_no=article_no, section=f"項{i+1}" if i > 0 else "",
                    law_name=law_name, jurisdiction="JP",
                ))
                chunk_index += 1
        else:
            chunks.append(_make_chunk(
                text=seg, doc_id=doc_id, chunk_index=chunk_index,
                article_no=article_no, section="",
                law_name=law_name, jurisdiction="JP",
            ))
            chunk_index += 1
    return chunks or _chunk_fixed(text, doc_id, law_name, "JP")


def _extract_jp_article_no(text: str) -> str:
    m = re.match(r"第([0-9０-９一二三四五六七八九十百千]+条(?:の[0-9０-９一二三四五六七八九十]+)?)", text)
    return m.group(1) if m else ""


def _split_at_jp_paragraph(text: str) -> List[str]:
    """Split a long 条 at 項 markers (２　or ２ at start of line)."""
    para_pat = re.compile(r"(?=^[２-９０-９]{1,2}　)", re.MULTILINE)
    parts = para_pat.split(text)
    # Merge tiny fragments into previous chunk
    result, buf = [], ""
    for part in parts:
        buf += part
        if len(buf) >= MAX_CHUNK_CHARS // 2:
            result.append(buf)
            buf = ""
    if buf:
        result.append(buf)
    return result if result else [text]


# ─── US statute chunker ───────────────────────────────────────────────────────

def _chunk_us_statute(text: str, doc_id: str, law_name: str) -> List[dict]:
    segments = _split_by_pattern(_US_SECTION, text)
    if len(segments) <= 1:
        return _chunk_fixed(text, doc_id, law_name, "US")

    chunks = []
    chunk_index = 0
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        article_no = _extract_us_section_no(seg)
        if len(seg) > MAX_CHUNK_CHARS:
            for sub in _split_fixed_overlap(seg):
                chunks.append(_make_chunk(
                    text=sub, doc_id=doc_id, chunk_index=chunk_index,
                    article_no=article_no, section="",
                    law_name=law_name, jurisdiction="US",
                ))
                chunk_index += 1
        else:
            chunks.append(_make_chunk(
                text=seg, doc_id=doc_id, chunk_index=chunk_index,
                article_no=article_no, section="",
                law_name=law_name, jurisdiction="US",
            ))
            chunk_index += 1
    return chunks or _chunk_fixed(text, doc_id, law_name, "US")


def _extract_us_section_no(text: str) -> str:
    m = re.match(r"(?:Section|Sec\.|§)\s*([\d.]+)", text)
    return m.group(1) if m else ""


# ─── Case law chunker ─────────────────────────────────────────────────────────

def _chunk_case(text: str, doc_id: str, law_name: str, jurisdiction: str) -> List[dict]:
    """Split case text at semantic sections: 事実/判旨/結論 (JP) or Facts/Held (US)."""
    jp_sections = re.compile(
        r"(?=(?:事実の概要|主文|理由|判示事項|裁判要旨|原審|当裁判所の判断))"
    )
    us_sections = re.compile(
        r"(?=(?:FACTS?|HELD|HOLDING|OPINION|BACKGROUND|DISCUSSION|CONCLUSION)[:\s])",
        re.IGNORECASE,
    )

    pattern = jp_sections if (jurisdiction == "JP" or _looks_jp(text)) else us_sections
    segments = _split_by_pattern(pattern, text)

    if len(segments) <= 1:
        return _chunk_fixed(text, doc_id, law_name, jurisdiction)

    chunks = []
    for i, seg in enumerate(segments):
        seg = seg.strip()
        if not seg:
            continue
        section_label = _extract_section_label(seg)
        for j, sub in enumerate(_split_fixed_overlap(seg) if len(seg) > MAX_CHUNK_CHARS else [seg]):
            chunks.append(_make_chunk(
                text=sub, doc_id=doc_id, chunk_index=len(chunks),
                article_no="", section=section_label,
                law_name=law_name, jurisdiction=jurisdiction,
            ))
    return chunks or _chunk_fixed(text, doc_id, law_name, jurisdiction)


def _extract_section_label(text: str) -> str:
    m = re.match(r"([^\s\n]{2,20})", text)
    return m.group(1) if m else ""


# ─── Contract chunker ─────────────────────────────────────────────────────────

def _chunk_contract(text: str, doc_id: str, law_name: str, jurisdiction: str) -> List[dict]:
    """Split contract at article/clause headings."""
    segments = _split_by_pattern(_CONTRACT_CLAUSE, text)
    if len(segments) <= 1:
        return _chunk_fixed(text, doc_id, law_name, jurisdiction)

    chunks = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        article_no = _extract_contract_article_no(seg)
        for sub in _split_fixed_overlap(seg) if len(seg) > MAX_CHUNK_CHARS else [seg]:
            chunks.append(_make_chunk(
                text=sub, doc_id=doc_id, chunk_index=len(chunks),
                article_no=article_no, section="",
                law_name=law_name, jurisdiction=jurisdiction,
            ))
    return chunks or _chunk_fixed(text, doc_id, law_name, jurisdiction)


def _extract_contract_article_no(text: str) -> str:
    m = re.match(r"(?:Article|ARTICLE|Clause|CLAUSE)\s+(\d+)|第([0-9０-９]+)条|\b(\d+)\.", text)
    if m:
        return m.group(1) or m.group(2) or m.group(3) or ""
    return ""


# ─── Fixed-size fallback ──────────────────────────────────────────────────────

def _chunk_fixed(
    text: str, doc_id: str, law_name: str, jurisdiction: str
) -> List[dict]:
    """Overlapping fixed-size character windows — safe fallback for any text."""
    chunks = []
    position = 0
    chunk_index = 0
    while position < len(text):
        end = min(position + MAX_CHUNK_CHARS, len(text))
        chunk = text[position:end].strip()
        if chunk:
            chunks.append(_make_chunk(
                text=chunk, doc_id=doc_id, chunk_index=chunk_index,
                article_no="", section="",
                law_name=law_name, jurisdiction=jurisdiction,
            ))
            chunk_index += 1
        position += MAX_CHUNK_CHARS - OVERLAP_CHARS
    return chunks


def _split_fixed_overlap(text: str) -> List[str]:
    """Split a long string into overlapping fixed-size windows."""
    parts = []
    pos = 0
    while pos < len(text):
        parts.append(text[pos: pos + MAX_CHUNK_CHARS])
        pos += MAX_CHUNK_CHARS - OVERLAP_CHARS
    return parts


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _split_by_pattern(pattern: re.Pattern, text: str) -> List[str]:
    """Split text at every match position (lookahead patterns keep the delimiter)."""
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return [text]
    segments = []
    prev = 0
    for pos in positions:
        if pos > prev:
            segments.append(text[prev:pos])
        prev = pos
    segments.append(text[prev:])
    return segments


def _looks_jp(text: str) -> bool:
    """Heuristic: text contains Japanese characters."""
    return any("\u3040" <= c <= "\u9FFF" for c in text[:500])


def _make_chunk(
    text: str,
    doc_id: str,
    chunk_index: int,
    article_no: str,
    section: str,
    law_name: str,
    jurisdiction: str,
) -> dict:
    return {
        "chunk_id":          str(uuid.uuid4()),
        "doc_id":            doc_id,
        "text":              text,
        "chunk_index":       chunk_index,
        "token_count_approx": len(text) // 4,
        "article_no":        article_no,
        "section":           section,
        "law_name":          law_name,
        "jurisdiction":      jurisdiction,
    }
