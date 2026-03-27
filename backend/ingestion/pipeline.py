"""Ingestion pipeline — orchestrates the full document → graph workflow.

Steps:
    1. Text extraction (PDF/DOCX/TXT/HTML)
    2. Chunking (512 tokens, 64 overlap)
    3. NER extraction (spaCy ja_ginza + en_core_web_trf)
    4. Graph node creation (neo4j-driver)
    5. Embedding indexing (multilingual-e5-large → Supabase pgvector)
"""

import io
from typing import Optional

from ingestion.chunker import chunk_text
from ingestion.ner import extract_entities
from ingestion.embedder import embed_chunks
from ingestion.graph_builder import build_graph_nodes


def run(
    content: bytes,
    doc_id: str,
    document_type: str,
    filename: Optional[str] = None,
    jurisdiction: str = "",
) -> dict:
    """Execute full ingestion pipeline for a document."""
    text = _extract_text(content, filename)
    chunks = chunk_text(text, doc_id, document_type=document_type, jurisdiction=jurisdiction)
    entities = extract_entities(text)
    graph_result = build_graph_nodes(
        chunks=chunks,
        entities=entities,
        doc_id=doc_id,
        document_type=document_type,
        filename=filename,
    )
    embed_result = embed_chunks(chunks)

    return {
        "doc_id": doc_id,
        "text_length": len(text),
        "chunk_count": len(chunks),
        "entity_count": len(entities),
        "graph_nodes_created": graph_result.get("nodes_created", 0),
        "vectors_indexed": embed_result.get("vectors_indexed", 0),
    }


def _extract_text(content: bytes, filename: Optional[str]) -> str:
    """Extract plain text from document bytes using pdfplumber (PDF) or python-docx (DOCX)."""
    ext = (filename or "").lower().rsplit(".", 1)[-1]

    if ext == "pdf":
        return _extract_pdf(content)

    if ext == "docx":
        return _extract_docx(content)

    # TXT / HTML / plain fallback
    return content.decode("utf-8", errors="ignore")


def _extract_pdf(content: bytes) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            return "\n\n".join(pages)
    except ImportError:
        # pdfplumber not installed — fall back to raw bytes decode
        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[pipeline] PDF extraction error: {e}")
        return content.decode("utf-8", errors="ignore")


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    except ImportError:
        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[pipeline] DOCX extraction error: {e}")
        return content.decode("utf-8", errors="ignore")
