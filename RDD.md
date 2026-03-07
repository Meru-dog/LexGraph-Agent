# LexGraph AI — Requirements Definition Document

> **Version:** 1.0 — Initial Release  
> **Date:** March 2025  
> **Status:** Draft — For Development Use  
> **Implementation Tool:** Claude Code  
> **Classification:** Confidential · Internal Use Only

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Frontend UI Requirements](#2-frontend-ui-requirements)
3. [Backend API Specification](#3-backend-api-specification)
4. [LangGraph Agent Specification](#4-langgraph-agent-specification)
5. [Neo4j Knowledge Graph Schema](#5-neo4j-knowledge-graph-schema)
6. [Fine-Tuning Specification](#6-fine-tuning-specification)
7. [Repository Structure](#7-repository-structure)
8. [Risk Register](#8-risk-register)
9. [Open Design Decisions](#9-open-design-decisions)

---

## 1. Project Overview

### 1.1 Purpose

LexGraph AI is a law firm-grade AI research and workflow automation platform supporting Japanese and US dual-jurisdiction legal practice. It combines **Graph RAG** (Neo4j-backed knowledge graph retrieval) with a **fine-tuned LLaMA 3.1 8B** language model to deliver legally precise, citation-grounded outputs across three core workflows:

- Legal research chat
- Due diligence automation (LangGraph agent)
- Contract review with redlining (LangGraph agent)

### 1.2 Core Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Frontend** | Next.js 14 (App Router) + Tailwind CSS | Chat UI, DD Agent UI, Contract Review diff viewer |
| **API** | FastAPI (Python 3.11) | REST endpoints: `/chat`, `/upload`, `/agent/dd`, `/agent/review`, `/graph` |
| **Graph DB** | Neo4j 5.x (AuraDB or Docker) | Legal knowledge graph: statutes, cases, concepts, relationships |
| **Vector Store** | FAISS (MVP) → Weaviate (prod) | Semantic chunk retrieval for Graph RAG |
| **LLM** | LLaMA 3.1 8B + QLoRA adapters | JP adapter + US adapter, routed at inference by jurisdiction |
| **Embeddings** | `multilingual-e5-large` | Handles Japanese and English in unified embedding space |
| **Agent Framework** | LangGraph | DD Agent and Contract Review Agent stateful workflows |
| **NER** | spaCy + `ja_ginza` (JP) / `en_core_web_trf` (US) | Entity extraction for graph construction pipeline |
| **Storage** | MinIO (local) / S3 (cloud) | Raw document storage before ingestion |
| **Orchestration** | Docker Compose (MVP) → Kubernetes | Service containerization and deployment |

### 1.3 Target Users

- Law firm associates and partners handling JP/US cross-border transactions
- Legal teams conducting M&A due diligence or corporate investment review
- Contract drafting and negotiation teams requiring AI-assisted redlining
- Legal researchers requiring citation-grounded statute and case law retrieval

### 1.4 Phased Roadmap

| Phase | Scope | Key Deliverables | Timeline | Exit Criteria |
|---|---|---|---|---|
| **Phase 0** | Infrastructure | Neo4j schema, ingestion pipeline, base Graph RAG | Weeks 1–4 | Upload PDF → nodes in Neo4j → RAG response via `/chat` |
| **Phase 1** | MVP UI | Chat UI, Upload UI, Graph Viewer | Weeks 5–7 | Non-technical user can upload doc and query it |
| **Phase 2** | LangGraph Agents | DD Agent + Contract Review Agent graphs | Weeks 8–11 | Both agents run end-to-end; human interrupt/resume works |
| **Phase 3** | Tool Implementation | Real graph/vector tools replacing mocks | Weeks 12–15 | Agents produce legally coherent outputs on real documents |
| **Phase 4** | LoRA Fine-tuning | JP + US QLoRA adapters trained and evaluated | Weeks 16–20 | Fine-tuned model outperforms base on COLIEE / LexGLUE |
| **Phase 5** | Agent UI | Attorney-facing task UI, human review interface, report export | Weeks 21–24 | Full workflow usable by attorney without dev intervention |
| **Phase 6** | Production | Auth/RBAC, audit logging, load testing | Weeks 25–30 | Production-ready deployment |

---

## 2. Frontend UI Requirements

The frontend is built with **Next.js 14 (App Router)** and **Tailwind CSS**. All pages share a persistent left sidebar navigation. The design language is **light mode** throughout.

### 2.1 Design Tokens

```css
/* Colors */
--primary:       #2D4FD6;
--navy:          #1E3A5F;
--accent:        #4F46E5;
--text-primary:  #111827;
--text-secondary:#374151;
--text-muted:    #6B7280;
--border:        #E5E7EB;
--border-light:  #F3F4F6;
--bg-page:       #F5F6F8;
--bg-card:       #FFFFFF;
--bg-subtle:     #F9FAFB;
--indigo-light:  #EEF2FF;
--indigo-border: #C7D2FA;

/* Risk colors */
--critical:      #DC2626;  --critical-bg: #FEF2F2;  --critical-border: #FECACA;
--high:          #EA580C;  --high-bg:     #FFF7ED;  --high-border:     #FED7AA;
--medium:        #D97706;  --medium-bg:   #FEFCE8;  --medium-border:   #FDE68A;
--ok:            #16A34A;  --ok-bg:       #F0FDF4;  --ok-border:       #BBF7D0;
```

```css
/* Typography — import from Google Fonts */
/* DM Serif Display      → branding, report titles */
/* IBM Plex Sans 300/400/500/600 → body text */
/* IBM Plex Mono 400/500 → code, citations, diffs, status badges */
```

### 2.2 Global Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Sidebar (220px fixed)  │  Main content area (flex 1)       │
│  ─────────────────────  │  ─────────────────────────────────│
│  LexGraph  [branding]   │  [Page-specific content]          │
│                         │                                   │
│  💬 Chat         ←active│                                   │
│  🔍 DD Agent            │                                   │
│  📄 Contract Review     │                                   │
│  🕸  Knowledge Graph    │                                   │
│  ⬆  Upload             │                                   │
│                         │                                   │
│  [Jurisdiction Badge]   │                                   │
└─────────────────────────────────────────────────────────────┘
```

**Sidebar specification:**

| Element | Spec |
|---|---|
| Background | `#FFFFFF`, right border `1px #E5E7EB` |
| Logo | `DM Serif Display`, 21px, `#111827` + subtitle 9.5px uppercase `#9CA3AF` |
| Nav item — default | `#6B7280` text, transparent bg, `2px solid transparent` left border |
| Nav item — hover | `#F1F3F8` background |
| Nav item — active | `#EEF2FF` bg, `#2D4FD6` text, `2px solid #2D4FD6` left border |
| Jurisdiction badge | `#F0F4FF` bg, `1px #C7D2FA` border, `#4F46E5` label, `#6B7280` value |
| Scrollbars | 5px width, `#D1D5DB` thumb, `#F1F3F5` track, 3px radius |

---

### 2.3 Chat Page (Home / Default View)

The Chat page is the **home screen**, rendered at `/`. It follows the ChatGPT/Claude conversation interface pattern.

#### Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│ Page Header: title + subtitle + topic chips                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Message thread — scrollable, max-width 740px centered]   │
│                                                             │
│  ⚖ Assistant bubble (white card, border, shadow)          │
│                                                             │
│       User bubble (indigo bg, white text)              [U] │
│                                                             │
│  ⚖ Typing indicator (3 animated dots)                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ Input area: textarea + send button                          │
│ Footer: model info                                          │
└─────────────────────────────────────────────────────────────┘
```

#### Component Specifications

| Component | Specification |
|---|---|
| **Page header** | White bar, `14px 24px` padding. Title: `"Legal Research Chat"` (15px, 600). Subtitle: `"Graph RAG · JP/US Law · LLaMA 3.1 Fine-tuned"` (11px, `#9CA3AF`). Right: topic chip buttons. |
| **Topic chips** | `Corporate Law`, `Securities (FIEA)`, `M&A`, `Contract`. Style: `#F5F7FF` bg, `1px #E0E4FA` border, 20px radius, `#4F46E5` text, 11px. Click → pre-fills input with `"Explain {topic} implications for "`. |
| **User message** | Avatar: 32px circle, `#2D4FD6` bg, white `"U"` (12px, 700). Bubble: `#2D4FD6` bg, white text, `12px 16px` padding, 10px radius. |
| **Assistant message** | Avatar: 32px circle, `#F0F4FF` bg, `#2D4FD6` `"⚖"` icon, `1px #C7D2FA` border. Bubble: white bg, `#374151` text, `1px #E5E7EB` border, `0 1px 3px rgba(0,0,0,0.04)` shadow, 14px font, 1.75 line-height. |
| **Typing indicator** | Three 7px circles, `#2D4FD6`, CSS keyframe animation — scale 0→1→0 at 0.2s stagger intervals. |
| **Input container** | `#F9FAFB` bg, `1px #E5E7EB` border, 12px radius. Inner: `textarea` (transparent, 14px, auto-resize 1–6 rows) + send button (36px square, `#2D4FD6`, `↑` arrow, hover darkens). |
| **Keyboard behavior** | `Enter` → send message. `Shift+Enter` → newline. Empty input → no submit. Auto-scroll to bottom on new message. |
| **Footer note** | `"LexGraph AI · JP/US Dual-Jurisdiction · Graph RAG + Fine-tuned LLaMA 3.1"`. Centered, 11px, `#D1D5DB`. |

#### Intent Routing (Frontend Mock Logic)

```typescript
const routeIntent = (input: string): string => {
  const lower = input.toLowerCase();
  if (lower.includes("dd") || lower.includes("due diligence"))
    return "→ directs user to DD Agent tab";
  if (lower.includes("contract"))
    return "→ directs user to Contract Review tab";
  if (lower.includes("会社法") || lower.includes("companies act"))
    return "→ Japanese Companies Act response";
  if (lower.includes("金商法") || lower.includes("fiea") || lower.includes("securities"))
    return "→ FIEA / securities law response";
  return "→ generic Graph RAG response";
};
```

---

### 2.4 DD Agent Page (`/dd`)

Attorneys enter a natural language prompt (e.g., *"Our company wants to invest ¥2B in TechCorp KK. Please conduct full legal DD as our lawyer."*) and the agent runs through 8 workflow steps, outputting a structured report in **CFI due diligence report format**.

#### Layout Structure

```
┌──────────────────────┬──────────────────────────────────────┐
│  Left Panel (296px)  │  Right Panel (flex)                  │
│  ──────────────────  │  ────────────────────────────────    │
│  [Prompt textarea]   │  [Empty state: run agent prompt]     │
│  [JP / US / JP+US]   │                                      │
│  [▶ Run DD Agent]    │  OR after completion:                │
│                      │                                      │
│  Workflow:           │  [Report Header Card]                │
│  ① Scope Planning ✓  │  [Risk Badge Summary]                │
│  ② Corporate Records │  [Recommendation Block]              │
│  ③ Financial Info ●  │                                      │
│  ④ Indebtedness      │  [§01 Corporate Records      ▼]      │
│  ⑤ Employment        │  [§02 Financial Information  ▶]      │
│  ⑥ Agreements        │  [§03 Indebtedness           ▶]      │
│  ⑦ Regulatory        │  ...                                 │
│  ⑧ Risk Synthesis    │  [§08 Legal & Regulatory     ▼]      │
│                      │                                      │
│                      │  [Attorney Disclaimer]               │
└──────────────────────┴──────────────────────────────────────┘
```

#### Left Panel Specifications

| Component | Specification |
|---|---|
| **Prompt textarea** | `84px` min-height, `#F9FAFB` bg, `1px #E5E7EB` border, 8px radius, 12px font, resizable. |
| **Jurisdiction toggle** | Three buttons: `JP` / `US` / `JP+US`. Active: `#EEF2FF` bg, `1px #C7D2FA` border, `#4F46E5` text. Inactive: `#F9FAFB` bg, gray text. |
| **Run button** | Full-width, `#2D4FD6` bg, white text, 13px 600. Loading state: `#E5E7EB` bg, gray text, `"⟳ Running DD Agent..."`. |

#### Workflow Stepper (8 Steps)

```
Step states:
  PENDING  → #F3F4F6 circle, gray number, #F0F2F5 connector line
  ACTIVE   → #EEF2FF circle, 2px #2D4FD6 border, animated pulse, #2D4FD6 "●"
  DONE     → #2D4FD6 filled circle, white "✓", #2D4FD6 connector line

Animation: step advances every 850ms after Run click.
           ddComplete = true after 700ms delay on final step.
```

| # | Step Label | Detail text |
|---|---|---|
| 1 | Scope Planning | Transaction type · Jurisdiction routing |
| 2 | Corporate Records Review | Entity registry · Cap table · Articles |
| 3 | Financial Information | Audited financials · Tax returns |
| 4 | Indebtedness Review | Loan agreements · Security interests |
| 5 | Employment & Labor | Officers · Compensation · Labor law |
| 6 | Agreements & Contracts | Scanning material contracts... |
| 7 | Regulatory & Legal | FSA · SEC · Litigation · Licenses |
| 8 | Risk Synthesis & Report | Aggregating findings → Final report |

#### Right Panel — Report Header Card

| Element | Specification |
|---|---|
| **Card** | White bg, `1px #E5E7EB` border, 10px radius, `26px 30px` padding, `0 1px 4px rgba(0,0,0,0.04)` shadow. |
| **Report label** | `"Due Diligence Report · Internal Memorandum"`. 10.5px, uppercase, `#9CA3AF`, letterSpacing 1.5. |
| **Target name** | `DM Serif Display`, 27px, `#111827`. |
| **Transaction** | 13px, `#6B7280`. |
| **Export button** | `#2D4FD6`, white, `"Export PDF"`, 12px 600, 8px radius. |
| **Metadata grid** | 4-column grid: Prepared By / Report Date / Jurisdiction / Total Findings. Each cell: `#F9FAFB` bg, `1px #F3F4F6` border, 8px radius, `11px 14px` padding. |
| **Risk badges** | Pill row: `N Critical` / `N High` / `N Medium` / `N Low/OK`. Color-coded bg + border + text (see tokens). |
| **Recommendation** | `#FFFBEB` bg, `1px #FDE68A` border, 8px radius. Label: `#92400E` 700. Body: `#78350F` 13px 1.65. |

#### Right Panel — Report Sections (×8)

CFI due diligence report format — 8 numbered collapsible sections:

| # | Section Title |
|---|---|
| 01 | Corporate Records |
| 02 | Financial Information |
| 03 | Indebtedness |
| 04 | Employment & Labor |
| 05 | Real Estate |
| 06 | Agreements & Contracts |
| 07 | Supplier & Customer Information |
| 08 | Legal & Regulatory |

**Section accordion header:**
- Section number badge: `#F0F4FF` bg, `#4F46E5` text, IBM Plex Mono, 9.5px 700
- Section title: 14px 600 `#111827`
- Status badge (if issues): CRITICAL / HIGH / MEDIUM pill (color-coded)
- Item count (right-aligned)
- Chevron ▼/▲

**Section body — finding rows:**

```
[STATUS BADGE] [Finding text — 13px, #374151, 1.7 line-height]

Status badge: 60px wide, IBM Plex Mono 9px 700, color-coded pill
  CRITICAL → #DC2626 text / #FEF2F2 bg / #FECACA border
  HIGH     → #EA580C text / #FFF7ED bg / #FED7AA border
  MEDIUM   → #D97706 text / #FEFCE8 bg / #FDE68A border
  OK       → #16A34A text / #F0FDF4 bg / #BBF7D0 border

Row bg: alternating white / #FAFAFA
Default open sections: 01 and 08
```

---

### 2.5 Contract Review Page (`/contract`)

Attorneys upload a contract and view an AI-generated redline comparison between the original and AI-reviewed version, using green/red diff styling (GitHub-style).

#### Layout Structure

```
┌──────────────────────┬──────────────────────────────────────┐
│  Left Panel (296px)  │  Right Panel (flex)                  │
│  ──────────────────  │  ────────────────────────────────    │
│  [Upload zone]       │  Toolbar: filename | [Split|Unified] │
│                      │  ──────────────────────────────────  │
│  OR after upload:    │                                      │
│                      │  SPLIT VIEW:                         │
│  ✓ filename.pdf      │  ┌──────────────┬─────────────────┐  │
│  [+14 add / -8 del]  │  │ − Original   │ + AI Redline    │  │
│                      │  │ (red header) │ (green header)  │  │
│  Counsel Notes:      │  │              │                 │  │
│  [§1 SERVICES  low]  │  │ removed lines│ added lines     │  │
│  [§2 PAYMENT   low]  │  │ in red bg    │ in green bg     │  │
│  [§3 IP       high]  │  │              │                 │  │
│  [§4 TERMINATION med]│  └──────────────┴─────────────────┘  │
│  [§5 LIABILITY  med] │                                      │
│  [§6 GOV LAW    med] │  OR UNIFIED VIEW:                    │
│                      │  [+ added lines in green]            │
│  [Export DOCX btn]   │  [− removed lines in red ]           │
│                      │  [  unchanged in gray     ]          │
└──────────────────────┴──────────────────────────────────────┘
```

#### Left Panel Specifications

| Component | Specification |
|---|---|
| **Upload zone (pre-upload)** | `2px dashed #D1D5DB` border, 10px radius, `36px 20px` padding. `📄` icon 32px, label, format hint. Click → trigger upload. Hover: `#2D4FD6` border + `#F5F7FF` bg. |
| **Success card** | `#F0FDF4` bg, `1px #BBF7D0` border, 8px radius. Filename (11px 600 `#15803D`) + subtitle. |
| **Count pills** | `+N additions` — green pill. `−N deletions` — red pill. Equal flex columns. |
| **Clause annotation card** | White bg, `1px #E5E7EB` border, 8px radius. Hover: `box-shadow 0 2px 8px rgba(0,0,0,0.07)`. Top row: clause ref (IBM Plex Mono 10px `#4F46E5` 600) + risk badge. Body: 11px `#6B7280` 1.55. |
| **Export button** | Full-width, `#2D4FD6`, `"Export Redlined DOCX"`, 12px 600. |

#### Diff Viewer — Split View

```
Left column header:  "− Original"       → #FEF2F2 bg, #DC2626 text, sticky
Right column header: "+ AI Redline..."  → #F0FDF4 bg, #15803D text, sticky

Line rendering (IBM Plex Mono 12px, 1.9 line-height):
  Removed line:  #FEF2F2 bg | 3px solid #EF4444 left border | #B91C1C text | "−" prefix
  Added line:    #F0FDF4 bg | 3px solid #22C55E left border | #15803D text | "+" prefix
  Same line:     transparent | 3px solid transparent       | #9CA3AF text | " " prefix

Left panel shows: same + removed lines (no added)
Right panel shows: same + added lines (no removed)
Both panels scroll independently, overflow: auto.
```

#### Diff Viewer — Unified View

```
Single scrollable column. Prefix column: 34px, IBM Plex Mono, center.

  Added line:    #F0FDF4 bg | 3px solid #22C55E left border | #16A34A "+" | #15803D text
  Removed line:  #FEF2F2 bg | 3px solid #EF4444 left border | #DC2626 "−" | #B91C1C text
  Same line:     transparent | 3px solid transparent        | #D1D5DB " " | #6B7280 text
```

#### Diff Algorithm

```typescript
// Line-by-line diff — implemented in lib/diff.ts
type DiffLine = { type: "same" | "added" | "removed"; text: string };

function diffLines(original: string, reviewed: string): DiffLine[] {
  const oLines = original.split("\n");
  const rLines = reviewed.split("\n");
  const result: DiffLine[] = [];
  let i = 0, j = 0;
  while (i < oLines.length || j < rLines.length) {
    const o = i < oLines.length ? oLines[i] : null;
    const r = j < rLines.length ? rLines[j] : null;
    if (o === r) {
      result.push({ type: "same", text: o! }); i++; j++;
    } else if (o !== null && (r === null || !rLines.slice(j).includes(o))) {
      result.push({ type: "removed", text: o }); i++;
    } else if (r !== null && (o === null || !oLines.slice(i).includes(r))) {
      result.push({ type: "added", text: r }); j++;
    } else {
      result.push({ type: "removed", text: o! });
      result.push({ type: "added", text: r! });
      i++; j++;
    }
  }
  return result;
}
```

---

### 2.6 Knowledge Graph Page (`/graph`)

Placeholder for Neo4j Bloom integration (Phase 3+).

| Component | Specification |
|---|---|
| **Empty state** | Centered: `🕸` (40px) + `"Knowledge Graph"` (DM Serif Display, 20px) + subtitle + Neo4j connection string badge (IBM Plex Mono, `#4F46E5`, white card). |
| **Phase 3 integration** | Neo4j Bloom embed via `<iframe>`, or custom D3.js force-directed graph. Node types rendered with distinct colors. Filter panel: jurisdiction, node type, date range. |

---

### 2.7 Upload Page (`/upload`)

| Component | Specification |
|---|---|
| **Drop zone** | `2px dashed #D1D5DB`, 12px radius, `48px 32px` padding, white bg. `⬆` icon (36px) + label + format types. Hover: `#2D4FD6` border + `#F5F7FF` bg. Drag-and-drop + click-to-browse. |
| **Document type selector** | 3-column grid: `Statute / Case Law / Contract / Regulation / SEC Filing / Other`. White bg, `1px #E5E7EB` border, 6px radius, 12px `#6B7280`. |
| **Supported formats** | PDF, DOCX, TXT, HTML. Max 50MB per file. |
| **Processing steps** | After upload: `Extracting text` → `Chunking (512 tokens, 64 overlap)` → `NER extraction` → `Graph node creation` → `Embedding indexing`. Each step shows spinner → checkmark. |

---

## 3. Backend API Specification

All endpoints served by **FastAPI (Python 3.11)**.

- **Development base URL:** `http://localhost:8000`
- **Production base URL:** `https://api.lexgraph.ai`
- **All responses:** JSON
- **Authentication:** Bearer JWT in `Authorization` header (Phase 6)

### 3.1 Endpoint Summary

| Method | Path | Description | Service |
|---|---|---|---|
| `POST` | `/upload` | Ingest document into graph + vector store | Ingestion Pipeline |
| `POST` | `/chat` | Graph RAG legal QA (streaming SSE) | Graph RAG + LLaMA |
| `POST` | `/agent/dd` | Start DD Agent workflow | LangGraph DDAgent |
| `GET` | `/agent/dd/{task_id}` | Poll DD Agent status + partial results | LangGraph State |
| `POST` | `/agent/dd/{task_id}/review` | Submit attorney review at human checkpoint | LangGraph `interrupt()` |
| `POST` | `/agent/review` | Start Contract Review Agent | LangGraph ContractAgent |
| `GET` | `/agent/review/{task_id}` | Poll Contract Review status | LangGraph State |
| `POST` | `/agent/review/{task_id}/approve` | Submit attorney clause approvals/redlines | LangGraph `interrupt()` |
| `GET` | `/graph/search` | Query Neo4j subgraph by entity/concept | Neo4j |
| `GET` | `/graph/node/{id}` | Fetch single node + neighbors | Neo4j |
| `GET` | `/health` | Health check | — |

### 3.2 `POST /chat`

**Request body:**
```json
{
  "query": "string",
  "jurisdiction": "JP | US | auto",
  "session_id": "string",
  "history": [{ "role": "user | assistant", "content": "string" }]
}
```

**Response (SSE stream, `text/event-stream`):**
```
data: {"token": "…"}
data: {"token": "…"}
data: {"done": true, "citations": [...], "subgraph_used": {...}, "adapter_used": "jp | us", "latency_ms": 1240}
```

**Citation object:**
```json
{
  "node_id": "string",
  "type": "Statute | Case | Provision",
  "title": "string",
  "article": "string",
  "url": "string | null"
}
```

### 3.3 `POST /agent/dd`

**Request body:**
```json
{
  "prompt": "string",
  "jurisdiction": "JP | US | both",
  "document_ids": ["string"],
  "transaction_type": "M&A | investment | loan | JV | other"
}
```

**Response `202 Accepted`:**
```json
{ "task_id": "string", "status": "running", "estimated_seconds": 90 }
```

**`GET /agent/dd/{task_id}` response:**
```json
{
  "task_id": "string",
  "status": "running | awaiting_review | complete | error",
  "current_step": 3,
  "step_label": "Agreements & Contracts",
  "partial_findings": [],
  "report": null
}
```

**`DDReport` schema (returned when `status === "complete"`):**
```json
{
  "target": "string",
  "transaction": "string",
  "date": "string",
  "jurisdiction": "string",
  "summary": {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 2,
    "recommendation": "string"
  },
  "sections": [
    {
      "num": "01",
      "title": "Corporate Records",
      "items": [
        { "status": "ok | warn | high | critical", "text": "string" }
      ]
    }
  ]
}
```

### 3.4 `POST /agent/review`

**Request body:**
```json
{
  "document_id": "string",
  "jurisdiction": "JP | US",
  "contract_type": "NDA | SPA | employment | license | MSA | other",
  "client_position": "buyer | seller | licensor | licensee | other"
}
```

**`GET /agent/review/{task_id}` response:**
```json
{
  "task_id": "string",
  "status": "running | awaiting_review | complete | error",
  "original_text": "string",
  "reviewed_text": "string",
  "diff": [{ "type": "same | added | removed", "text": "string" }],
  "clause_reviews": [],
  "compliance_flags": []
}
```

**`ClauseReview` schema:**
```json
{
  "clause_id": "string",
  "clause_type": "payment | ip | termination | liability | governing_law | ...",
  "original_text": "string",
  "reviewed_text": "string",
  "risk_level": "critical | high | medium | low",
  "issues": ["string"],
  "redline_suggestion": "string",
  "applicable_statutes": ["string"],
  "citations": ["string"]
}
```

---

## 4. LangGraph Agent Specification

### 4.1 DD Agent — State Schema

```python
from typing import TypedDict, List, Dict, Optional
from langchain_core.messages import BaseMessage

class Finding(TypedDict):
    status: str          # "critical" | "high" | "warn" | "ok"
    text: str
    section: str
    citations: List[str]

class RiskMatrix(TypedDict):
    critical: List[Finding]
    high: List[Finding]
    medium: List[Finding]
    low: List[Finding]

class DDReport(TypedDict):
    target: str
    transaction: str
    date: str
    jurisdiction: str
    summary: dict
    sections: List[dict]

class DDState(TypedDict):
    # Input
    transaction_type: str
    jurisdiction: str           # "JP" | "US" | "both"
    documents: List[dict]
    prompt: str

    # Planning
    dd_checklist: List[dict]

    # Sub-investigation outputs (populated in parallel)
    corporate_findings: List[Finding]
    contract_findings: List[Finding]
    regulatory_findings: List[Finding]

    # Synthesis
    risk_matrix: RiskMatrix

    # Human loop
    attorney_notes: str
    approved: bool
    reinvestigation_targets: List[str]

    # Output
    dd_report: Optional[DDReport]
    messages: List[BaseMessage]
```

### 4.2 DD Agent — Node Graph

```
START
  │
  ▼
scope_planner ──────────────────────────────────────────────┐
  │                                                          │
  ▼                                                          │
  ├──── Send() ──► corporate_reviewer ──────────────┐       │
  │                                                  │       │
  ├──── Send() ──► contract_reviewer ───────────────┤       │
  │                                                  │       │
  └──── Send() ──► regulatory_checker ──────────────┘       │
                                                    │       │
                                         fan-in     │       │
                                                    ▼       │
                                           risk_synthesizer │
                                                    │       │
                                                    ▼       │
                                           human_checkpoint │
                                           (interrupt())    │
                                              │         │   │
                                           approved   rejected
                                              │         │
                                              ▼         ▼
                                     report_generator  re_investigate
                                              │         │
                                              │         └──► risk_synthesizer
                                              ▼
                                            END
```

| Node | Responsibility | Tools Used |
|---|---|---|
| `scope_planner` | Parse prompt → transaction type + DD checklist | LLM + `jurisdiction_router` |
| `corporate_reviewer` | Entity docs, cap table, board minutes | `graph_search`, `vector_search`, `statute_lookup` |
| `contract_reviewer` | Material contract risk analysis | `clause_segmenter`, `risk_classifier`, `vector_search` |
| `regulatory_checker` | Statute cross-reference check | `statute_lookup`, `graph_search`, `cross_reference_checker` |
| `risk_synthesizer` | Aggregate sub-agent outputs → risk matrix | LLM synthesis |
| `human_checkpoint` | `interrupt()` — pause, await `/agent/dd/{id}/review` | LangGraph `interrupt()` |
| `re_investigate` | Deep-dive on attorney-flagged items | All tools, loops to `risk_synthesizer` |
| `report_generator` | Format 8-section CFI-format DD report | LLM + `report_formatter` |

### 4.3 Contract Review Agent — State Schema

```python
class Clause(TypedDict):
    id: str
    type: str           # "payment" | "ip" | "termination" | "liability" | ...
    text: str
    position: int       # character offset in original

class ClauseReview(TypedDict):
    clause_id: str
    risk_level: str     # "critical" | "high" | "medium" | "low"
    issues: List[str]
    redline_suggestion: str
    applicable_statutes: List[str]
    citations: List[str]

class Inconsistency(TypedDict):
    clause_a_id: str
    clause_b_id: str
    description: str

class ComplianceFlag(TypedDict):
    clause_id: str
    statute: str
    issue: str
    severity: str

class ContractReviewState(TypedDict):
    # Input
    raw_contract: str
    jurisdiction: str
    contract_type: str
    client_position: str

    # Parsing
    clauses: List[Clause]

    # Per-clause review
    clause_reviews: List[ClauseReview]

    # Cross-reference
    inconsistencies: List[Inconsistency]

    # Statute compliance
    compliance_flags: List[ComplianceFlag]

    # Human loop
    attorney_redlines: Dict[str, str]   # clause_id → attorney text
    approved_clauses: List[str]

    # Output
    redlined_contract: str
    review_report: dict
    messages: List[BaseMessage]
```

### 4.4 Contract Review Agent — Node Graph

```
START
  │
  ▼
parser ──► clause_classifier ──► review_loop (iterate over clauses)
                                      │
                                      ▼
                               cross_ref_checker
                                      │
                                  inconsistency? ──YES──► review_loop (re-enter)
                                      │ NO
                                      ▼
                               statute_checker (Neo4j graph lookup per clause)
                                      │
                                      ▼
                               human_checkpoint (interrupt())
                                      │
                                      ▼
                               redline_generator ──► END
```

| Node | Responsibility | Tools |
|---|---|---|
| `parser` | Segment contract into typed clauses | `clause_segmenter`, LLM |
| `clause_classifier` | Map clause → type (payment, IP, termination…) | LLM classifier |
| `review_loop` | Per-clause: risk score + issues + redline suggestion | LLM + `graph_search` |
| `cross_ref_checker` | Internal inconsistency detection | `cross_reference_checker` |
| `statute_checker` | Validate each clause vs Neo4j statutes | `graph_search`, `statute_lookup` |
| `human_checkpoint` | `interrupt()` — attorney reviews high-risk clauses | LangGraph `interrupt()` |
| `redline_generator` | Build final diff + DOCX export | LLM + `report_formatter` |

### 4.5 Shared Tool Registry

```python
# All tools are @tool decorated functions registered in a shared ToolRegistry

def graph_search(query: str, jurisdiction: str, node_types: List[str]) -> SubGraph:
    """Traverse Neo4j subgraph. Backend: py2neo Cypher."""

def vector_search(query: str, jurisdiction: str, top_k: int = 5) -> List[Chunk]:
    """Semantic chunk retrieval. Backend: FAISS."""

def statute_lookup(article_ref: str, jurisdiction: str) -> Provision:
    """Direct article fetch. Backend: Neo4j + e-Gov API fallback."""

def risk_classifier(text: str, context: str) -> RiskLevel:
    """Score legal risk. Backend: Fine-tuned LLaMA (QLoRA adapter)."""

def clause_segmenter(text: str, contract_type: str) -> List[Clause]:
    """Split contract into typed clauses. Backend: regex + LLM correction."""

def cross_reference_checker(clauses: List[Clause]) -> List[Inconsistency]:
    """Detect internal inconsistencies. Backend: embedding similarity matrix."""

def jurisdiction_router(text: str) -> Literal["JP", "US"]:
    """Detect jurisdiction. Backend: langdetect + explicit tag handler."""

def human_review_interrupt(state: AgentState, reason: str) -> None:
    """Pause graph, notify via WebSocket. Backend: LangGraph interrupt()."""

def report_formatter(findings: List[Finding], template: str) -> str:
    """Generate structured report. Backend: LLM + Jinja2."""
```

---

## 5. Neo4j Knowledge Graph Schema

### 5.1 Node Labels and Properties

| Label | Key Properties | Jurisdiction |
|---|---|---|
| `Statute` | `title`, `article_no`, `effective_date`, `jurisdiction`, `text`, `source_url` | JP / US |
| `Case` | `court`, `docket_no`, `date`, `holding`, `jurisdiction`, `summary` | JP / US |
| `Provision` | `text`, `parent_statute`, `article_no`, `section`, `paragraph_no` | JP / US |
| `LegalConcept` | `name`, `domain`, `definition`, `aliases` | JP / US / Both |
| `Entity` | `name`, `entity_type` (corp/person/agency), `jurisdiction` | JP / US |
| `Regulation` | `title`, `issuer`, `effective_date`, `jurisdiction`, `text` | JP / US |
| `Chunk` | `text`, `embedding_id`, `source_doc_id`, `position`, `token_count` | JP / US |

### 5.2 Relationship Types

| Relationship | From → To | Semantics |
|---|---|---|
| `CITES` | Case → Case \| Statute | Precedent citation in judgment text |
| `INTERPRETS` | Case → Provision | Judicial interpretation of statutory provision |
| `AMENDS` | Statute → Statute | Legislative amendment relationship |
| `IMPLEMENTS` | Regulation → Statute | Delegated legislation / enabling act |
| `OVERRULES` | Case → Case | Precedent reversal (US: stare decisis) |
| `ANALOGOUS_TO` | Concept → Concept | Cross-jurisdictional concept mapping (Phase 3) |
| `GOVERNS` | Statute → LegalConcept | Regulatory scope over a legal concept |
| `INVOLVES` | Case → Entity | Party relationship to case |
| `CHUNK_OF` | Chunk → Statute \| Case | Document chunk belongs to source node |

### 5.3 Sample Cypher — Graph RAG Query

```cypher
-- Graph RAG retrieval: anchor from vector search result, 2-hop traversal
MATCH (anchor {node_id: $anchor_id})
CALL apoc.path.subgraphAll(anchor, {
  relationshipFilter: "CITES|INTERPRETS|AMENDS|IMPLEMENTS|GOVERNS",
  maxLevel: 2
})
YIELD nodes, relationships
RETURN nodes, relationships
LIMIT 50
```

### 5.4 Cross-Jurisdictional Concept Alignment (Phase 3)

`ANALOGOUS_TO` edges require manual legal review — semantic similarity alone is insufficient.

| JP Concept | US Concept | Alignment Type |
|---|---|---|
| 不法行為 (Civil Code Art.709) | Tort / Negligence | Structural analogy |
| 取締役の善管注意義務 | Duty of Care (Delaware) | Functional equivalence |
| 金融商品取引法 | Securities Exchange Act 1934 | Regulatory parallel |
| 株主代表訴訟 (Art.847) | Derivative suit | Procedural analogy |
| 職務発明 (Patent Act Art.35) | Work-for-hire (17 USC §101) | Functional analogy, differs in mechanism |
| 三六協定 | FLSA overtime authorization | Regulatory parallel, significant differences |

---

## 6. Fine-Tuning Specification

### 6.1 Base Model and QLoRA Config

| Parameter | Value |
|---|---|
| **Base model** | LLaMA 3.1 8B (Swallow-8B as JP fallback — Tohoku University JP continued pretraining) |
| **Method** | QLoRA: 4-bit NF4 quantization + LoRA adapters |
| **LoRA rank** | `r=16`, `alpha=32`, `dropout=0.05` |
| **Target modules** | `q_proj`, `v_proj`, `k_proj`, `o_proj` |
| **Training framework** | HuggingFace `transformers` + `peft` + `trl` (SFTTrainer) |
| **Hardware** | Single A100 40GB or 2× A10G. Est. 4–6 hours per adapter. |
| **Adapter strategy** | `adapter_us/` (US 1,800 examples) + `adapter_jp/` (JP 1,800 examples). Selected at inference by `jurisdiction_router`. |

### 6.2 US Training Datasets

| Dataset | HF Path | Examples | Focus Area | Priority |
|---|---|---|---|---|
| CUAD | `cuad` | 600 | US commercial contracts, 41 clause types | ⭐⭐⭐⭐⭐ |
| Edgar-Corpus | `eloukas/edgar-corpus` | 300 | Securities filings: 10-K, 8-K, proxies | ⭐⭐⭐⭐⭐ |
| LegalBench | `nguha/legalbench` | 400 | Legal reasoning, contracts, interpretation | ⭐⭐⭐⭐⭐ |
| CaseHOLD | `casehold` | 200 | Federal court decisions, holding selection | ⭐⭐⭐⭐ |
| ContractNLI | `contract-nli` | 150 | Contract clause NLI / interpretation | ⭐⭐⭐⭐ |
| BillSum | `billsum` | 150 | Congressional bills / regulatory text | ⭐⭐⭐ |
| **Total** | | **1,800** | | |

### 6.3 Japanese Training Datasets

| Dataset | Source | Examples | Focus Area | Priority |
|---|---|---|---|---|
| JLawText | `legalscape/jlawtext` | 500 | 会社法 · 金商法 statutes | ⭐⭐⭐⭐⭐ |
| e-Gov API | Government API | 400 | Current Japanese laws (all ministries) | ⭐⭐⭐⭐⭐ |
| JCourts | `legalscape/jcourts` | 300 | Corporate case law (商事判例) | ⭐⭐⭐⭐ |
| Courts.go.jp | Web scraping* | 200 | Supreme Court (最高裁) decisions | ⭐⭐⭐⭐⭐ |
| FSA Regulations | FSA website | 200 | Financial regulations (金融庁) | ⭐⭐⭐⭐ |
| JP Contract Templates | Synthetic | 200 | Contract Q&A | ⭐⭐⭐ |
| **Total** | | **1,800** | | |

> \* Verify `courts.go.jp` `robots.txt` and Terms of Service before scraping. Use `legalscape/jcourts` as primary fallback.

### 6.4 Instruction Format (SFTTrainer)

```json
{
  "instruction": "You are a legal expert in Japanese corporate law. Answer the following question with precise statutory citations.",
  "input": "What are the requirements for a director's duty of care under the Companies Act?",
  "output": "Under the Japanese Companies Act Art. 355, directors owe a duty of care (善管注意義務) to the company, requiring..."
}
```

### 6.5 Evaluation Benchmarks

| Benchmark | Jurisdiction | Target Metric |
|---|---|---|
| COLIEE Task 4 — Statute Entailment | JP | > 70% accuracy (baseline LLaMA ~55%) |
| LexGLUE Multi-task | US | > 75% macro-F1 across 6 tasks |
| Internal contract test set (20 contracts) | JP + US | Lawyer blind review ≥ 4/5 |

---

## 7. Repository Structure

```
lexgraph-ai/                          ← Root monorepo
│
├── frontend/                         ← Next.js 14 application
│   ├── app/
│   │   ├── page.tsx                  ← Chat (home screen)
│   │   ├── dd/page.tsx               ← DD Agent
│   │   ├── contract/page.tsx         ← Contract Review
│   │   ├── graph/page.tsx            ← Knowledge Graph
│   │   └── upload/page.tsx           ← Document Upload
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   └── PageHeader.tsx
│   │   ├── chat/
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   └── ChatInput.tsx
│   │   ├── dd/
│   │   │   ├── DDPromptPanel.tsx
│   │   │   ├── StepProgress.tsx
│   │   │   ├── DDReportHeader.tsx
│   │   │   ├── DDReportSection.tsx   ← Collapsible accordion section
│   │   │   └── RiskBadge.tsx
│   │   └── contract/
│   │       ├── UploadZone.tsx
│   │       ├── ClauseAnnotationCard.tsx
│   │       ├── DiffViewer.tsx        ← Split + Unified views
│   │       └── DiffLine.tsx
│   ├── hooks/
│   │   ├── useChat.ts
│   │   ├── useDDAgent.ts             ← Polling /agent/dd/{task_id}
│   │   ├── useContractReview.ts
│   │   └── useWebSocket.ts           ← Human checkpoint notifications
│   ├── lib/
│   │   ├── api.ts                    ← API client (fetch wrappers)
│   │   ├── diff.ts                   ← diffLines() algorithm
│   │   └── types.ts                  ← Shared TypeScript types
│   └── tailwind.config.ts
│
├── backend/                          ← FastAPI application
│   ├── main.py                       ← FastAPI app init, router mounts
│   ├── api/routers/
│   │   ├── chat.py                   ← POST /chat (SSE streaming)
│   │   ├── upload.py                 ← POST /upload
│   │   ├── agent_dd.py               ← POST/GET /agent/dd
│   │   ├── agent_review.py           ← POST/GET /agent/review
│   │   └── graph.py                  ← GET /graph/*
│   ├── agents/
│   │   ├── dd_agent.py               ← LangGraph DDAgent graph definition
│   │   ├── review_agent.py           ← LangGraph ContractReviewAgent
│   │   └── state.py                  ← DDState, ContractReviewState TypedDicts
│   ├── tools/
│   │   ├── graph_search.py
│   │   ├── vector_search.py
│   │   ├── statute_lookup.py
│   │   ├── risk_classifier.py
│   │   ├── clause_segmenter.py
│   │   ├── cross_reference_checker.py
│   │   ├── jurisdiction_router.py
│   │   └── report_formatter.py
│   ├── ingestion/
│   │   ├── pipeline.py               ← Orchestrates full ingestion flow
│   │   ├── chunker.py                ← 512 token chunks, 64 overlap
│   │   ├── ner.py                    ← spaCy NER (ja_ginza + en_core_web_trf)
│   │   ├── embedder.py               ← multilingual-e5-large
│   │   └── graph_builder.py          ← py2neo node/edge creation
│   ├── graph/
│   │   ├── neo4j_client.py
│   │   ├── schema.py                 ← Node/relationship definitions
│   │   └── cypher_queries.py         ← Parameterized Cypher templates
│   └── models/
│       ├── llama_client.py           ← LLaMA inference (vLLM or transformers)
│       ├── adapter_router.py         ← JP/US LoRA adapter selection
│       └── embedding_client.py       ← multilingual-e5-large client
│
├── training/                         ← Fine-tuning pipeline
│   ├── datasets/
│   │   ├── us_loader.py              ← CUAD, LegalBench, CaseHOLD, etc.
│   │   ├── jp_loader.py              ← JLawText, JCourts, e-Gov, FSA
│   │   └── format_instructions.py    ← Instruction tuning format
│   ├── finetune_us.py                ← QLoRA training: US adapter
│   ├── finetune_jp.py                ← QLoRA training: JP adapter
│   └── evaluate.py                   ← COLIEE + LexGLUE evaluation runner
│
├── docker-compose.yml                ← Neo4j + FastAPI + MinIO + FAISS
├── pyproject.toml
└── docs/
    ├── RDD.md                        ← This document
    └── architecture.md
```

---

## 8. Risk Register

| Risk | Severity | Mitigation | Owner |
|---|---|---|---|
| LLaMA hallucination on specific article citations | 🔴 CRITICAL | Citation grounding layer: always verify cited articles against Neo4j before returning response. | Backend / LLM |
| `courts.go.jp` scraping legal risk | 🟠 HIGH | Verify `robots.txt` and ToS. Use `legalscape/jcourts` HF dataset as primary; web scraping as supplement only. | Data team |
| Agent loop non-termination (contract review edge case) | 🟠 HIGH | Max iteration guard on clause review loop. Fallback to human checkpoint after N iterations without convergence. | Agent team |
| LoRA adapter quality insufficient for JP legal domain | 🟡 MEDIUM | Swallow-8B as base model fallback. Evaluate after first training run before committing to LLaMA 3.1. | ML team |
| Neo4j graph quality degradation over time | 🟡 MEDIUM | Ingestion validation pipeline with entity resolution checks. Periodic consistency audit Cypher queries. Versioned snapshots. | Data team |
| Primary enterprise customer revenue concentration (DD pattern) | 🟡 MEDIUM | Agent correctly identifies and flags as HIGH risk. Human attorney checkpoint before report finalization. | Agent team |
| LLM inference latency exceeding attorney tolerance | 🟢 LOW | SSE streaming for chat. Background async for agents. Targets: first token < 2s, full DD report < 90s. | Infra team |

---

## 9. Open Design Decisions

| # | Decision | Options | Recommendation | Deadline |
|---|---|---|---|---|
| 1 | JP base model | LLaMA 3.1 8B vs Swallow-8B (JP continued pretraining) | Swallow for JP-heavy use. LLaMA 3.1 if US primary. | Phase 4 start |
| 2 | Jurisdiction routing | Hard-coded `langdetect` rules vs LLM-based classifier | Hybrid: `langdetect` + explicit tag; LLM for ambiguous queries | Phase 3 |
| 3 | Graph RAG strategy | Microsoft GraphRAG (community) vs explicit edge-typed graph | Explicit edge-typed: legal relational structure is known *a priori* | Phase 0 |
| 4 | LangGraph state backend | In-memory / PostgreSQL / Redis | PostgreSQL for production; in-memory for Phase 2 dev | Phase 2 |
| 5 | LLM in agents during dev | OpenAI API (fast iteration) → fine-tuned LLaMA (production) | OpenAI GPT-4o in Phases 2–3; swap to LLaMA in Phase 4 | Phase 2 |
| 6 | Redline export format | DOCX tracked changes vs JSON diff vs custom HTML | DOCX tracked changes — attorneys expect this format | Phase 5 |
| 7 | Clause segmentation | Pure rule-based vs LLM-based vs hybrid | Hybrid: regex for structural boundaries + LLM for semantic correction | Phase 3 |

---

*Document Control: v1.0 — Initial Release — March 2025. Confidential — Internal development use only. To be implemented using Claude Code.*