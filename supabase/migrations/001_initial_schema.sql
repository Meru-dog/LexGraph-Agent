-- LexGraph AI — Initial Supabase Schema
-- Run via: supabase db push  OR  paste into Supabase SQL editor

-- ── pgvector extension ──────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS vector;

-- ── documents ───────────────────────────────────────────────────────────────
-- Stores metadata for uploaded client documents.
-- Files are stored in Supabase Storage; this table tracks ingestion status.

CREATE TABLE IF NOT EXISTS documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID,                           -- references auth.users(id)
    file_name    TEXT NOT NULL,
    file_path    TEXT NOT NULL,                  -- Supabase Storage path
    doc_type     TEXT,                           -- contract | statute | case | other
    jurisdiction TEXT,                           -- JP | US
    uploaded_at  TIMESTAMPTZ DEFAULT now(),
    processed    BOOLEAN DEFAULT false
);

-- ── chunks ───────────────────────────────────────────────────────────────────
-- Document chunks with multilingual-e5-large embeddings (1024-dim).
-- status: ACTIVE | ARCHIVED  — ARCHIVED chunks are excluded from search.
-- effective_date: used to exclude statutes not yet in force.

CREATE TABLE IF NOT EXISTS chunks (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id       TEXT UNIQUE,                  -- application-level ID (doc_id + offset)
    document_id    UUID REFERENCES documents(id) ON DELETE CASCADE,
    text           TEXT NOT NULL,
    embedding      vector(1024),                 -- multilingual-e5-large
    source_type    TEXT,                         -- Statute | Case | Contract | Other
    law_name       TEXT,
    article_no     TEXT,
    jurisdiction   TEXT,                         -- JP | US
    status         TEXT DEFAULT 'ACTIVE',        -- ACTIVE | ARCHIVED
    effective_date DATE,
    version        INTEGER DEFAULT 1,
    created_at     TIMESTAMPTZ DEFAULT now()
);

-- IVFFlat index for fast approximate nearest-neighbour search.
-- lists=100 is suitable for up to ~1M vectors; tune after data grows.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Metadata filter indexes
CREATE INDEX IF NOT EXISTS chunks_jurisdiction_idx ON chunks (jurisdiction);
CREATE INDEX IF NOT EXISTS chunks_status_idx        ON chunks (status);
CREATE INDEX IF NOT EXISTS chunks_chunk_id_idx      ON chunks (chunk_id);

-- ── match_chunks (pgvector RPC) ──────────────────────────────────────────────
-- Similarity search with metadata filtering.
-- Called by backend/ingestion/embedder.py search_chunks().

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding  vector(1024),
    match_count      int             DEFAULT 5,
    filter_jurisdiction TEXT         DEFAULT NULL,
    filter_status    text            DEFAULT 'ACTIVE'
)
RETURNS TABLE (
    id             UUID,
    chunk_id       TEXT,
    document_id    UUID,
    text           TEXT,
    source_type    TEXT,
    law_name       TEXT,
    article_no     TEXT,
    jurisdiction   TEXT,
    status         TEXT,
    effective_date DATE,
    score          FLOAT8
)
LANGUAGE sql STABLE AS $$
    SELECT
        c.id,
        c.chunk_id,
        c.document_id,
        c.text,
        c.source_type,
        c.law_name,
        c.article_no,
        c.jurisdiction,
        c.status,
        c.effective_date,
        1 - (c.embedding <=> query_embedding) AS score
    FROM chunks c
    WHERE c.status = filter_status
      AND (filter_jurisdiction IS NULL OR c.jurisdiction = filter_jurisdiction)
      AND (c.effective_date IS NULL OR c.effective_date <= CURRENT_DATE)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ── ragas_scores ─────────────────────────────────────────────────────────────
-- RAGAS evaluation results — used for regression testing and W&B logging.

CREATE TABLE IF NOT EXISTS ragas_scores (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluated_at      TIMESTAMPTZ DEFAULT now(),
    pipeline_version  TEXT,
    faithfulness      FLOAT,
    answer_relevancy  FLOAT,
    context_precision FLOAT,
    context_recall    FLOAT,
    test_count        INTEGER,
    notes             TEXT
);

-- ── route_logs ───────────────────────────────────────────────────────────────
-- Self-Route router debug log — stores routing decisions for analysis.

CREATE TABLE IF NOT EXISTS route_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query       TEXT,
    route_used  TEXT,
    confidence  FLOAT,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);
