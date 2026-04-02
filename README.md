# LexGraph Agent

**Graph RAG legal research platform for JP/US dual-jurisdiction practice.**

LexGraph Agent combines a Neo4j knowledge graph, Supabase pgvector search, and a local Qwen3 Swallow 8B LLM (via Ollama) to help attorneys and paralegals perform due diligence, contract review, and legal research across Japanese and US law. All client document processing runs locally to maintain attorney-client privilege (守秘義務).

---

## Key Features

| Feature | Description |
|---|---|
| **Legal Chat** | SSE-streaming Q&A with Self-Route classification (5 routes) and hybrid retrieval |
| **DD Agent** | 8-node LangGraph due diligence workflow with parallel investigation and attorney approval gate |
| **Contract Review** | AI redlining with clause-by-clause risk annotations, diff viewer, and DOCX export |
| **Knowledge Graph** | D3.js force-directed visualization with node filtering, expansion, and status color coding |
| **Graph Quality Dashboard** | Admin metrics: ARCHIVED ratio, orphaned nodes, unverified nodes (>90d), integrity checks |
| **Document Upload** | PDF/DOCX ingestion → statute-aware chunking → NER → graph nodes → pgvector embeddings |
| **RAGAS Evaluation** | 25 JP/US test cases, 4 metrics (Faithfulness/Relevancy/Precision/Recall), W&B logging |
| **Fine-tuning Pipeline** | QLoRA training (LoRA rank-16) with W&B experiment tracking and GGUF export for Ollama |
| **JWT Auth + RBAC** | Attorney / paralegal / admin roles with audit logging |
| **Rate Limiting** | Per-IP sliding-window rate limiter (configurable) |
| **e-Gov Amendment Monitor** | Check Japanese law amendments via e-Gov API with auto-archive capability |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js 15 (App Router)  — localhost:3000                  │
│  Chat · DD · Contract · Tasks · Graph · Quality · Upload    │
└────────────────────┬────────────────────────────────────────┘
                     │ REST + SSE + WebSocket
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI (Python 3.11)  — localhost:8000                    │
│  /auth  /chat  /upload  /agent/dd  /agent/review           │
│  /graph  /evaluate/ragas  /ws/{session_id}                  │
│                                                             │
│  Self-Router (5 routes) → HybridRetriever (4 stages)       │
│  LangGraph agents  ←→  Qwen3 Swallow 8B (Ollama)          │
│  Tools: graph_search · vector_search · statute_lookup       │
│         risk_classifier · clause_segmenter · report_fmt     │
└──────┬───────────────────┬──────────────────┬──────────────┘
       │                   │                  │
┌──────▼──────┐   ┌───────▼────────┐  ┌──────▼──────┐
│   Neo4j 5   │   │   Supabase     │  │   Ollama    │
│  knowledge  │   │   pgvector     │  │  Qwen3 8B   │
│   graph     │   │   (1024-dim)   │  │  (local)    │
└─────────────┘   └────────────────┘  └─────────────┘
```

### Retrieval Pipeline

```
Query → Self-Router (5 routes + multi-hop regex signals)
      → HybridRetriever:
          ① pgvector semantic search (multilingual-e5-large)
          ② Neo4j FULLTEXT keyword search
          ③ APOC 2-hop BFS graph traversal
          ④ CrossEncoder reranking (ms-marco-MiniLM-L-6-v2)
      → LLM synthesis with LEGAL_SYSTEM_PROMPT
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 · React 18 · Tailwind CSS · TypeScript |
| **Backend** | FastAPI · LangGraph · python-jose (JWT) · reportlab · python-docx |
| **Graph DB** | Neo4j 5 (APOC, fulltext indexes) |
| **Vector Store** | Supabase pgvector (1024-dim, multilingual-e5-large) |
| **LLM (primary)** | Qwen3 Swallow 8B RL via Ollama — local, confidentiality-safe |
| **LLM (optional)** | Gemini 2.5 Flash — non-confidential data only |
| **Embeddings** | multilingual-e5-large (sentence-transformers) |
| **Evaluation** | RAGAS + W&B (projects: lexgraph-rag, lexgraph-finetune) |
| **Fine-tuning** | HuggingFace transformers + peft + trl (QLoRA) |

---

## Prerequisites

- Python 3.11+
- Node.js 20+ (pnpm recommended)
- Docker + Docker Compose (for Neo4j)
- [Ollama](https://ollama.com/) with `qwen3-swallow:8b` model
- Supabase project (for pgvector + auth) — or run without for dev mode

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/Meru-dog/LexGraph-Agent
cd LexGraph-Agent
cp .env.example .env
```

Edit `.env`:

```env
# Required
JWT_SECRET_KEY=<random-32-hex>        # openssl rand -hex 32
NEO4J_PASSWORD=lexgraph_dev

# Ollama (default: localhost:11434)
OLLAMA_MODEL=qwen3-swallow:8b

# Supabase (for pgvector + auth)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

# Optional: Gemini for non-confidential tasks
GEMINI_API_KEY=AIza...
```

### 2. Start Ollama + Neo4j

```bash
# Start Ollama and pull the model
ollama serve &
ollama pull qwen3-swallow:8b

# Start Neo4j
docker compose up neo4j -d
```

### 3. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install spaCy models
python -m spacy download en_core_web_sm
# Optional — Japanese NER (~500 MB):
pip install ja-ginza

# Run
python main.py
```

API: `http://localhost:8000` | Docs: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
pnpm install   # or npm install
pnpm dev
```

Open `http://localhost:3000`.

### 5. Log in

| Username | Password | Role |
|---|---|---|
| `admin` | `secret` | admin |
| `attorney1` | `secret` | attorney |
| `paralegal1` | `secret` | paralegal |

---

## Docker Compose (full stack)

```bash
cp .env.example .env   # set required vars
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Neo4j Browser | http://localhost:7474 |

---

## Testing

```bash
cd backend
pip install pytest
python -m pytest tests/ -v
```

Tests cover: Self-Router classification, structural chunker, adapter router, model factory, report formatter, RAGAS heuristic evaluator, and more.

---

## API Endpoints

```
Auth
  POST  /auth/login                  Login (form body: username, password)
  POST  /auth/refresh                Refresh access token
  GET   /auth/me                     Current user info

Chat
  POST  /chat                        SSE streaming legal Q&A (supports force_route override)
  GET   /chat/classify?q=...         Debug: classify query via Self-Router

Documents
  POST  /upload                      Upload PDF/DOCX for ingestion
  POST  /ingest/{doc_id}             Trigger pgvector embedding

DD Agent
  POST  /agent/dd                    Start DD analysis (returns task_id)
  GET   /agent/dd/{task_id}          Poll status + partial findings
  POST  /agent/dd/{task_id}/review   Attorney approve / return
  GET   /agent/dd/{task_id}/export   Download DD report (PDF)
  GET   /agent/dd/models             List available LLM models

Contract Review
  POST  /agent/review                Start contract review
  GET   /agent/review/{task_id}      Poll status + clause reviews
  POST  /agent/review/{task_id}/approve   Attorney redlines
  GET   /agent/review/{task_id}/export    Download redlined contract (DOCX)

Knowledge Graph
  GET   /graph/stats                 Node/relationship counts
  GET   /graph/sample?limit=60       Subgraph for visualization
  GET   /graph/node/{id}?hops=2      Node + N-hop neighborhood
  GET   /graph/search?q=...          Full-text + graph search
  GET   /graph/quality               Quality dashboard metrics (§10.6)
  GET   /graph/integrity             Run 4 integrity checks (§10.4)
  POST  /graph/check-amendments      Check e-Gov API for law amendments

Evaluation
  POST  /evaluate/ragas              Start RAGAS evaluation (background job)
  GET   /evaluate/ragas/{job_id}     Poll evaluation results
  GET   /evaluate/ragas/history/latest   Recent RAGAS scores from Supabase

WebSocket
  WS    /ws/{session_id}             Real-time task status updates
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3-swallow:8b` | Primary local LLM model |
| `FINE_TUNED_MODEL` | `lexgraph-legal:latest` | Fine-tuned adapter model |
| `JP_ADAPTER_MODEL` | `lexgraph-legal-jp:latest` | JP jurisdiction adapter |
| `US_ADAPTER_MODEL` | `lexgraph-legal-us:latest` | US jurisdiction adapter |
| `JWT_SECRET_KEY` | `dev-secret-...` | **Change in production** |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `lexgraph_dev` | Neo4j password |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Supabase service role key |
| `GEMINI_API_KEY` | — | Optional: Gemini for non-confidential tasks |
| `RATE_LIMIT_REQUESTS` | `60` | Max requests per window per IP |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window duration |
| `AUDIT_LOG_PATH` | `./data/audit.jsonl` | Audit log file path |

---

## Project Structure

```
LexGraph-Agent/
├── backend/
│   ├── main.py                    # FastAPI entry + rate limiter
│   ├── agents/
│   │   ├── dd_agent.py            # LangGraph DD (8 nodes, parallel + fan-in)
│   │   ├── review_agent.py        # LangGraph contract review (7 nodes)
│   │   └── state.py               # Shared TypedDicts (DDState, ReviewState)
│   ├── api/
│   │   ├── auth/                  # JWT, bcrypt, RBAC
│   │   ├── audit/                 # Append-only JSONL logger
│   │   ├── export/                # PDF (reportlab) + DOCX (python-docx)
│   │   └── routers/               # chat, upload, agent_dd, agent_review, graph, evaluate, ws, auth
│   ├── evaluation/
│   │   ├── ragas_evaluator.py     # LexGraphEvaluator + W&B + regression check
│   │   └── test_cases.py          # 25 JP/US legal QA pairs
│   ├── fine_tune/
│   │   ├── train_lora.py          # QLoRA training (W&B integrated)
│   │   ├── export_gguf.py         # GGUF export for Ollama
│   │   ├── evaluate_finetune.py   # Base vs fine-tuned RAGAS comparison (W&B)
│   │   └── generate_training_data.py  # Training data generation
│   ├── graph/
│   │   ├── neo4j_client.py        # Neo4j driver wrapper
│   │   ├── schema.py              # Constraints + indexes
│   │   ├── cypher_queries.py      # Graph RAG + integrity check queries
│   │   ├── metadata.py            # AmendmentManager + integrity checks
│   │   └── seed.py                # JP/US statute seed data
│   ├── ingestion/
│   │   ├── pipeline.py            # Upload → extract → chunk → embed
│   │   ├── chunker.py             # Statute-aware (条/項, Section/§, Clause)
│   │   ├── embedder.py            # multilingual-e5-large → pgvector
│   │   └── graph_builder.py       # NER → Neo4j nodes
│   ├── models/
│   │   ├── model_factory.py       # Unified LLM factory (ollama/gemini/adapters)
│   │   ├── llama_lc.py            # Ollama ChatOllama wrapper + thinking mode
│   │   ├── adapter_router.py      # JP/US adapter auto-selection
│   │   └── gemini_lc.py           # Gemini LangChain wrapper
│   ├── retrieval/
│   │   └── hybrid_retriever.py    # 4-stage: pgvector → keyword → BFS → rerank
│   ├── tools/
│   │   ├── self_router.py         # 5-route classifier + multi-hop regex
│   │   ├── graph_search.py        # Neo4j subgraph search
│   │   ├── vector_search.py       # pgvector similarity search
│   │   ├── statute_lookup.py      # Article reference resolver
│   │   ├── egov_monitor.py        # e-Gov API amendment checker
│   │   └── report_formatter.py    # DD/contract report builder
│   └── tests/                     # pytest test suites
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Chat (route override, model selector)
│   │   ├── dd/page.tsx            # DD Agent (stepper + report + PDF export)
│   │   ├── contract/page.tsx      # Contract Review (diff + DOCX export)
│   │   ├── graph/page.tsx         # Knowledge Graph (D3 canvas)
│   │   ├── graph/quality/page.tsx # Graph Quality Dashboard
│   │   ├── tasks/page.tsx         # Task Dashboard
│   │   ├── upload/page.tsx        # Document Upload
│   │   └── login/page.tsx         # Auth
│   ├── components/                # chat/, dd/, contract/, layout/
│   ├── context/                   # Auth, Chat, DD, ContractReview contexts
│   ├── hooks/                     # useContractReview, useWebSocket
│   └── lib/                       # api.ts, types.ts, diff.ts
├── docker-compose.yml
├── RDD.md                         # Requirements Design Document v3.0
└── .env.example
```

---

## W&B Monitoring

Two W&B projects track experiments.

### 0) One-time setup (required for correct RAGAS → W&B logging)

```bash
cd backend
pip install -r requirements.txt
wandb login
```

Recommended `.env` for evaluation runs:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-swallow:8b
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

If W&B is not needed for a run, set `use_wandb=false` in the API request (see below).

### `lexgraph-rag` — RAG quality

Beginner-friendly local JSON evaluation (separate from backend startup):

```bash
cd backend
mkdir -p eval_data
python eval_ragas.py --eval-data eval_data/sample_eval.json
```

`eval_ragas.py` uses Gemini for RAGAS evaluation LLM/embeddings. Set `GEMINI_API_KEY` in `backend/.env` before running.
If your account/model access differs, set `GEMINI_EMBEDDING_MODEL` (default: `models/embedding-001`).

`backend/eval_ragas.py` reads JSON entries in this format:

```json
[
  {
    "question": "質問文",
    "contexts": ["根拠テキスト1", "根拠テキスト2"],
    "reference": "模範回答"
  }
]
```

When your real answer function is ready, pass it with `--generator module:function`:

```bash
python eval_ragas.py --generator your_module:generate_answer
```

You should see `RAGAS result:` and `scores to wandb:` in terminal output, then the run in W&B (`job_type=eval`).

```bash
cd backend
python -c "from evaluation.ragas_evaluator import LexGraphEvaluator; LexGraphEvaluator(pipeline_version='v1', use_wandb=True).run()"
```

Logs: 4 RAGAS metrics, JP/US breakdown, per-case table, failure cases, regression check (fails if Faithfulness drops >5%).

API alternative (same evaluator, async job):

```bash
# Start evaluation job
curl -X POST http://localhost:8000/evaluate/ragas \
  -H "Content-Type: application/json" \
  -d '{"pipeline_version":"v1","use_local_llm":true,"use_wandb":true}'

# Poll status
curl http://localhost:8000/evaluate/ragas/<job_id>
```

### `lexgraph-finetune` — Fine-tuning

```bash
# Train (logs loss curve, LR, grad norm, adapter artifact)
python fine_tune/train_lora.py --base_model Qwen/Qwen2.5-1.5B-Instruct --adapter JP --eval_ragas

# Build evaluation set (custom test cases + optional Hugging Face samples)
python -m evaluation.build_eval_dataset --max_examples 120 --include_hf --output eval_data/legal_eval_4way.json

# 4-way comparison (A/B/C/D): base/ft × no-RAG/RAG
python fine_tune/evaluate_finetune.py \
  --base_model qwen2.5:1.5b \
  --finetuned_model lexgraph-legal \
  --eval_dataset eval_data/legal_eval_4way.json \
  --max_examples 8 \
  --ragas_timeout_sec 180 \
  --ragas_max_workers 1 \
  --version v2
```

Key metrics: `train/loss`, condition metrics (`A_base_no_rag/*` ... `D_ft_rag/*`),
and decomposition deltas (`delta/ft_effect_no_rag/*`, `delta/rag_effect_base/*`, etc.).

Recommended rollout to avoid timeout storms: 8 → 20 → 40 → full dataset.

Troubleshooting:

- If metrics are all zeros, confirm Ollama is running and `OLLAMA_MODEL` is available.
- If Ollama logs show `POST /api/chat 404`, the configured `OLLAMA_MODEL` is not installed on your machine; run `ollama pull <model>` or change `OLLAMA_MODEL` in `.env`.
- If W&B logs are missing, re-run `wandb login` in the same shell/session.
- If Supabase history endpoint is empty, check `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.

---

## Confidentiality Model

```
Client documents (contracts, filings)
  → MUST stay on local machine
  → Ollama inference only (no cloud API)
  → Supabase Storage = encrypted at rest (legal equivalent to Google Drive)

Public data (laws, cases, HF datasets)
  → MAY use cloud APIs (e-Gov, HuggingFace, Gemini)
  → Training data sourced from public datasets only
```

---

## License

MIT
