# LexGraph AI

**Graph RAG legal research platform for Japanese and US dual-jurisdiction practice.**

LexGraph AI combines a Neo4j knowledge graph, FAISS vector search, and a Gemini-powered LLM to help attorneys and paralegals perform due diligence, contract review, and legal research across JP and US law — all in a single platform with a human-in-the-loop review workflow.

---

## Key Features

| Feature | Description |
|---|---|
| **Legal Chat** | SSE-streaming Q&A with citations from the knowledge graph and vector index |
| **DD Agent** | 8-section CFI-format due diligence report (LangGraph, human approval gate) |
| **Contract Review** | AI redlining with clause-by-clause risk annotations and DOCX export |
| **Knowledge Graph** | Neo4j graph of statutes, provisions, entities, and cross-jurisdictional analogies |
| **Document Upload** | PDF/DOCX ingestion → NER → graph embedding pipeline |
| **Task Dashboard** | Real-time attorney task monitor with WebSocket status updates |
| **JWT Auth + RBAC** | Attorney / paralegal / admin roles; paralegals cannot approve reviews |
| **Audit Log** | Append-only JSONL log of every login, upload, agent run, approval, and export |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js 14 (App Router)  — localhost:3000                  │
│  Chat · DD Agent · Contract Review · Tasks · Graph · Upload │
└────────────────────┬────────────────────────────────────────┘
                     │ REST + SSE + WebSocket
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI (Python 3.11)  — localhost:8000                    │
│  /auth  /chat  /upload  /agent/dd  /agent/review            │
│  /graph  /ws/{session_id}                                   │
│                                                             │
│  LangGraph agents  ←→  Gemini 1.5 Pro                       │
│  Tools: vector_search · graph_search · statute_lookup       │
│         risk_classifier · clause_segmenter · report_fmt     │
└──────┬──────────────────────────┬───────────────────────────┘
       │                          │
┌──────▼──────┐          ┌────────▼────────┐
│   Neo4j 5   │          │   FAISS index   │
│  knowledge  │          │  (multilingual  │
│   graph     │          │   E5-large)     │
└─────────────┘          └─────────────────┘
```

**Tech stack:**

- **Backend:** FastAPI · LangGraph · python-jose (JWT) · passlib (bcrypt) · pdfplumber · python-docx · reportlab · spaCy (ja_ginza + en_core_web_trf)
- **Frontend:** Next.js 14 · React 18 · Tailwind CSS · TypeScript
- **Storage:** Neo4j 5 (graph + fulltext index) · FAISS (vector) · MinIO (raw documents, optional)
- **LLM:** Google Gemini 1.5 Pro (default) — swappable to vLLM/LLaMA via `USE_VLLM=true`

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose (for Neo4j and MinIO)
- A [Google AI Studio](https://aistudio.google.com/app/apikey) API key

---

## Local Setup

### 1. Clone and configure

```bash
git clone https://github.com/your-org/lexgraph-ai.git
cd lexgraph-ai
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
GEMINI_API_KEY=AIza...          # required
JWT_SECRET_KEY=<random-32-hex>  # generate: openssl rand -hex 32
NEO4J_PASSWORD=lexgraph_dev     # matches docker-compose default
```

### 2. Start infrastructure (Neo4j + MinIO)

```bash
docker compose up neo4j minio -d
```

Wait ~30 s for Neo4j to finish starting. You can verify at `http://localhost:7474` (user: `neo4j`, password: `lexgraph_dev`).

### 3. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# — or with Poetry —
pip install poetry && poetry install --without training

# Install spaCy language models
python -m spacy download en_core_web_sm
# Optional — Japanese NER (requires ~500 MB):
pip install ja-ginza

# Run
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### 5. Log in

Use the built-in development accounts:

| Username | Password | Role |
|---|---|---|
| `attorney1` | `secret` | attorney |
| `paralegal1` | `secret` | paralegal |
| `admin` | `secret` | admin |

> **Production:** replace the in-memory user store in `backend/api/auth/models.py` with a real database lookup and rotate `JWT_SECRET_KEY`.

---

## Docker Compose (full stack)

```bash
cp .env.example .env   # add GEMINI_API_KEY
docker compose up --build
```

Services:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |
| MinIO console | http://localhost:9001 |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** Google AI Studio key |
| `GEMINI_MODEL` | `gemini-1.5-pro` | Model ID |
| `JWT_SECRET_KEY` | `dev-secret-...` | **Change in production** |
| `JWT_ACCESS_EXPIRE_MINUTES` | `60` | Access token TTL |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token TTL |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `lexgraph_dev` | Neo4j password |
| `USE_VLLM` | `false` | Set `true` to use local LLaMA via vLLM |
| `LLAMA_ENDPOINT` | `http://localhost:8080` | vLLM server URL |
| `AUDIT_LOG_PATH` | `./data/audit.jsonl` | Audit log output path |

---

## Project Structure

```
lexgraph-ai/
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── agents/
│   │   ├── dd_agent.py           # LangGraph DD agent (8 nodes + human gate)
│   │   └── review_agent.py       # LangGraph contract review agent
│   ├── api/
│   │   ├── auth/                 # JWT, bcrypt, RBAC dependencies
│   │   ├── audit/                # Append-only JSONL audit logger
│   │   ├── export/               # PDF (reportlab) + DOCX (python-docx) export
│   │   └── routers/              # FastAPI routers (auth, chat, upload, agents, graph, ws)
│   ├── graph/                    # Neo4j client, schema, Cypher queries, seed data
│   ├── ingestion/                # PDF/DOCX pipeline, NER (spaCy), FAISS embedder
│   ├── models/                   # Gemini LangChain adapter, vLLM client
│   └── tools/                    # Agent tools: vector/graph search, statute lookup,
│                                 #   risk classifier, clause segmenter, report formatter
├── frontend/
│   ├── app/                      # Next.js pages (chat, dd, contract, tasks, graph, upload, login)
│   ├── components/               # UI components (chat, dd, contract, layout)
│   ├── context/                  # AuthContext (JWT session management)
│   ├── hooks/                    # useChat, useDDAgent, useContractReview, useWebSocket
│   └── lib/                      # api.ts, auth.ts, types, diff utilities
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## API Overview

```
POST  /auth/login              Login (form body: username, password)
POST  /auth/refresh            Refresh access token
GET   /auth/me                 Current user info

POST  /chat                    SSE streaming legal Q&A
POST  /upload                  Upload PDF/DOCX for ingestion
POST  /ingest/{doc_id}         Trigger FAISS embedding for a document

POST  /agent/dd                Start DD analysis
GET   /agent/dd/{id}           Poll DD task status
POST  /agent/dd/{id}/review    Attorney approve / return for re-investigation
GET   /agent/dd/{id}/export    Download DD report as PDF

POST  /agent/review            Start contract review
GET   /agent/review/{id}       Poll review task status
GET   /agent/review/{id}/export Download redlined contract as DOCX

GET   /graph/search            Full-text + graph search
GET   /graph/node/{id}         Node + 1-hop neighborhood

WS    /ws/{session_id}         Real-time task status updates
```

All endpoints except `/auth/login` and `/health` require a `Bearer` token.

---

## Seed Data

On first startup, the backend seeds the Neo4j graph with:

- **6 statutes:** 会社法, 金融商品取引法, 民法, DGCL, Securities Act 1933, Securities Exchange Act 1934
- **10 key provisions** including fiduciary duty, insider trading, M&A approval articles
- **4 cross-jurisdictional concept pairs** (e.g. 忠実義務 ↔ Fiduciary Duty)

---

## License

MIT
# LexGraph-Agent
