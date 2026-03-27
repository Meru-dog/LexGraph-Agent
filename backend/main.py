"""LexGraph AI — FastAPI application entry point."""

import os
from pathlib import Path

# Load .env before anything else so GEMINI_API_KEY and other vars are available.
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

# Prevent tokenizer multiprocessing workers from deadlocking inside asyncio.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import time
import collections
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import chat, upload, agent_dd, agent_review, graph, ws, auth, evaluate

# ── In-memory sliding-window rate limiter (per IP) ──────────────────────────
# Env vars: RATE_LIMIT_REQUESTS (default 60), RATE_LIMIT_WINDOW_SECONDS (default 60)
_RL_MAX = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
_RL_WIN = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
_rl_buckets: dict = collections.defaultdict(collections.deque)   # ip → deque of timestamps


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
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://lexgraph.ai"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Sliding-window per-IP rate limiter (RDD §16 production hardening).

    Limits: RATE_LIMIT_REQUESTS requests per RATE_LIMIT_WINDOW_SECONDS seconds.
    /health is exempt. Localhost (127.0.0.1) bypasses in dev.
    """
    ip = request.client.host if request.client else "unknown"

    # Exempt: health checks and local dev
    if request.url.path == "/health" or ip in ("127.0.0.1", "::1"):
        return await call_next(request)

    now = time.monotonic()
    bucket = _rl_buckets[ip]

    # Evict timestamps outside the window
    while bucket and now - bucket[0] > _RL_WIN:
        bucket.popleft()

    if len(bucket) >= _RL_MAX:
        retry_after = int(_RL_WIN - (now - bucket[0])) + 1
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Retry after {retry_after}s."},
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    return await call_next(request)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(agent_dd.router)
app.include_router(agent_review.router)
app.include_router(graph.router)
app.include_router(ws.router)
app.include_router(evaluate.router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import pathlib
    import uvicorn

    # google-generativeai touches hundreds of protobuf files on import, triggering
    # watchfiles when reload watches the full CWD. Fix: pass absolute paths so
    # watchfiles watches ONLY the source subdirs, never .venv.
    _here = pathlib.Path(__file__).parent
    _src_dirs = [
        str(_here / d)
        for d in ("api", "agents", "graph", "ingestion", "models", "tools")
        if (_here / d).is_dir()
    ]

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=_src_dirs,
    )
