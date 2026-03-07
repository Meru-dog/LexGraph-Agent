"""LexGraph AI — FastAPI application entry point."""

import os
# Prevent tokenizer multiprocessing workers from deadlocking inside asyncio.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import chat, upload, agent_dd, agent_review, graph, ws, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    _connect_neo4j()
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
    _disconnect_neo4j()


def _connect_neo4j():
    try:
        from graph.neo4j_client import neo4j_client
        from graph.schema import apply_schema
        from graph.seed import seed
        neo4j_client.connect()
        if neo4j_client._driver:
            apply_schema(neo4j_client)
            print("[main] Neo4j schema applied")
            seed(neo4j_client)
    except Exception as e:
        print(f"[main] Neo4j startup error (non-fatal): {e}")


def _warmup_models():
    """Pre-load ML models on the main thread to avoid SIGSEGV when loading from worker threads."""
    try:
        from ingestion.embedder import _get_model, _get_index
        _get_model()
        _get_index()
    except Exception as e:
        print(f"[main] Model warmup error (non-fatal): {e}")


def _disconnect_neo4j():
    try:
        from graph.neo4j_client import neo4j_client
        neo4j_client.close()
    except Exception:
        pass


app = FastAPI(
    title="LexGraph AI API",
    description="Graph RAG legal research platform for JP/US dual-jurisdiction practice",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://lexgraph.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(agent_dd.router)
app.include_router(agent_review.router)
app.include_router(graph.router)
app.include_router(ws.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
