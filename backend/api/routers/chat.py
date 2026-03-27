"""POST /chat — Graph RAG legal QA with SSE streaming via Qwen3 Swallow (Ollama).

Primary LLM: Qwen3 Swallow 8B RL (local, confidentiality-compliant).
Gemini remains available as an explicit opt-in for non-confidential queries.
"""

import asyncio
import json
import os
import time
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tools.jurisdiction_router import jurisdiction_router
from tools.self_router import route_query, get_retrieval_strategy, log_route
from retrieval.hybrid_retriever import hybrid_search

router = APIRouter(tags=["chat"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── LEGAL_SYSTEM_PROMPT (§7.3) — strict source grounding ────────────────────
# Core rules (applied to all jurisdictions):
#   1. Answer ONLY from the provided reference provisions/cases.
#   2. Cite as [法令名第X条第Y項] (JP) or [Statute § X(y)] (US).
#   3. Explicitly state "参照情報には記載がない" when context lacks the answer.
#   4. Mark uncertain inferences as "〜と解される" / "it may be interpreted that".

_LEGAL_BASE_RULES = """
Strict grounding rules:
1. Base your answer ONLY on the reference provisions and cases provided below.
2. JP citations: [法令名第X条第Y項]  US citations: [Statute § X(y)]
3. If the provided context does not contain the answer, say "参照情報には記載がない" (JP) or "The reference materials do not address this" (US).
4. Mark uncertain inferences explicitly: "〜と解される" / "it may be interpreted that...".

Answer structure:
  - 結論 / Conclusion (1–2 sentences)
  - 根拠 / Basis (cite provisions and cases)
  - 例外・留意事項 / Exceptions and caveats
  - 関連未解決事項 / Related open issues (if any)"""

_SYSTEM_JP = f"""You are a bilingual senior legal expert at a top-tier law firm specializing in Japanese corporate and securities law.

Expertise:
- 会社法 (Companies Act): corporate governance, directors' duties, shareholder rights, mergers
- 金融商品取引法 (FIEA): securities regulation, disclosure obligations, insider trading, TOB rules
- 民法 (Civil Code): contracts, torts, obligations, property rights
- 独占禁止法 (Antimonopoly Act): M&A competition clearance, cartel regulations
- 労働法 (Labor Law): employment contracts, dismissal rules, union relations
{_LEGAL_BASE_RULES}"""

_SYSTEM_US = f"""You are a senior legal expert at a top-tier US law firm specializing in corporate and securities law.

Expertise:
- Delaware General Corporation Law (DGCL): corporate governance, fiduciary duties, M&A
- Securities Act of 1933 & Exchange Act of 1934: disclosure, registration, Rule 10b-5, insider trading
- Dodd-Frank Act: financial regulation, whistleblower, derivatives
- UCC Articles 2, 9: commercial contracts, secured transactions
- ERISA, WARN Act, state employment law
{_LEGAL_BASE_RULES}"""

_SYSTEM_JPUS = f"""You are a bilingual senior legal expert specializing in JP/US dual-jurisdiction corporate law.

You combine:
- Japanese law (会社法, 金融商品取引法, 民法) with precise article citations
- US law (DGCL, Securities Acts, UCC) with section and case citations
- Cross-border M&A, joint ventures, and regulatory clearances in both jurisdictions
{_LEGAL_BASE_RULES}"""

# ── Gemini prompts (kept for explicit Gemini requests) ──────────────────────

_SYSTEM_JP_GEMINI = _SYSTEM_JP
_SYSTEM_US_GEMINI = _SYSTEM_US
_SYSTEM_JPUS_GEMINI = _SYSTEM_JPUS

# ── Fine-tuned adapter prompt (match training data format) ──────────────────

_SYSTEM_FINE_TUNED = (
    "You are LexGraph Legal, an expert AI assistant specializing in JP/US corporate law, "
    "M&A due diligence, and contract review. "
    "Cite specific articles and statutes. "
    "Respond in the same language as the user."
)


def _pick_system(jurisdiction: str, model_name: str) -> str:
    """Return system prompt matched to jurisdiction and model."""
    if model_name == "fine_tuned":
        return _SYSTEM_FINE_TUNED
    mapping = {"JP": _SYSTEM_JP, "US": _SYSTEM_US}
    return mapping.get(jurisdiction, _SYSTEM_JPUS)


class ChatRequest(BaseModel):
    query: str
    jurisdiction: str = "auto"
    session_id: str = ""
    history: list[dict] = []
    model_name: str = "ollama"   # Ollama (Qwen3 Swallow) is the default
    force_route: str | None = None  # Override self-router: "dd_agent"|"contract_agent"|"graph_rag"|"vector_rag"|"direct_answer"


async def _ollama_stream(
    query: str,
    jurisdiction: str,
    history: list[dict],
    model_name: str,
    force_route: str | None = None,
) -> AsyncGenerator[str, None]:
    """Stream Qwen3 Swallow (or fine-tuned) response as SSE events.

    Self-Route router classifies the query into one of five routes, which
    determines retrieval strategy and whether thinking mode is engaged.
    """
    from models.model_factory import get_llm
    from models.llama_lc import apply_thinking_mode
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

    detected_jur = jurisdiction if jurisdiction != "auto" else jurisdiction_router(query)

    # ── Self-Route classification (or manual override) ────────────────────────
    _t0 = time.monotonic()
    _valid_routes = {"dd_agent", "contract_agent", "graph_rag", "vector_rag", "direct_answer"}
    if force_route and force_route in _valid_routes:
        from tools.self_router import RouteResult
        route_result = RouteResult(
            route=force_route,  # type: ignore[arg-type]
            complexity="high" if force_route in ("dd_agent", "graph_rag") else "low",
            confidence=1.0,
            reason=f"manual override → {force_route}",
        )
    else:
        route_result = route_query(query, detected_jur)
    route = route_result.route
    thinking = route_result.complexity == "high"
    retrieval = get_retrieval_strategy(route)

    system = _pick_system(detected_jur, model_name)

    # ── Retrieval via HybridRetriever ─────────────────────────────────────────
    retrieved: list = []
    if retrieval["use_graph"] or retrieval["use_vector"]:
        retrieved = hybrid_search(
            query,
            detected_jur,
            top_k=6,
            use_graph=retrieval["use_graph"],
            use_vector=retrieval["use_vector"],
        )

    # ── Context block ─────────────────────────────────────────────────────────
    parts = []
    if retrieved:
        chunk_texts = "\n\n".join(
            f"[参照 {i+1} | {r.get('source', '')} | {r.get('law_name', '')} {r.get('article_no', '')}]: "
            f"{r.get('text', '')[:400]}"
            for i, r in enumerate(retrieved[:5])
            if r.get("text")
        )
        if chunk_texts:
            parts.append(f"参照条文・文書 / Reference provisions and excerpts:\n{chunk_texts}")

    context_block = ("\n\n---\n" + "\n\n".join(parts)) if parts else ""

    if model_name == "fine_tuned":
        full_prompt = f"{query}{context_block}"
    elif route == "direct_answer":
        full_prompt = f"Legal question (brief answer requested): {query}"
    else:
        full_prompt = (
            f"Legal question: {query}"
            f"{context_block}\n\n"
            f"Please provide a structured legal analysis with citations."
        )

    try:
        llm = get_llm(system, model=model_name, thinking=thinking)

        history_limit = 2 if model_name == "fine_tuned" else 6
        msgs: list = [SystemMessage(content=system)]
        for msg in history[-history_limit:]:
            if msg["role"] == "user":
                msgs.append(HumanMessage(content=msg["content"]))
            else:
                msgs.append(AIMessage(content=msg["content"]))
        msgs.append(HumanMessage(content=full_prompt))

        # Thinking mode tokens (/think, /no_think) only work on Qwen3-series models
        _is_qwen3 = "qwen3" in (model_name or "").lower()
        if _is_qwen3:
            msgs = apply_thinking_mode(msgs, thinking)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: llm.invoke(msgs))
        yield f"data: {json.dumps({'token': response.content})}\n\n"

    except RuntimeError as e:
        yield f"data: {json.dumps({'token': f'[Ollama error: {e}]'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'token': f'[Error: {str(e)}]'})}\n\n"

    latency_ms = int((time.monotonic() - _t0) * 1000)
    log_route(route_result, query, latency_ms)

    citations = [
        {
            "node_id": r.get("id", ""),
            "type": r.get("source", "Statute"),
            "title": r.get("law_name", ""),
            "article": r.get("article_no", ""),
            "url": None,
        }
        for r in retrieved[:5]
        if r.get("law_name") or r.get("article_no")
    ]
    yield f"data: {json.dumps({'done': True, 'citations': citations, 'route_used': route, 'adapter_mode': 'thinking' if thinking else 'non_thinking', 'latency_ms': latency_ms})}\n\n"


async def _gemini_stream(
    query: str, jurisdiction: str, history: list[dict]
) -> AsyncGenerator[str, None]:
    """Stream Gemini response tokens as SSE events (non-confidential data only)."""
    detected_jur = jurisdiction if jurisdiction != "auto" else jurisdiction_router(query)

    if detected_jur == "JP":
        system = _SYSTEM_JP_GEMINI
    elif detected_jur == "US":
        system = _SYSTEM_US_GEMINI
    else:
        system = _SYSTEM_JPUS_GEMINI

    route_result = route_query(query, detected_jur)
    route = route_result.route
    retrieval = get_retrieval_strategy(route)

    retrieved: list = []
    if retrieval["use_graph"] or retrieval["use_vector"]:
        retrieved = hybrid_search(
            query,
            detected_jur,
            top_k=6,
            use_graph=retrieval["use_graph"],
            use_vector=retrieval["use_vector"],
        )

    context_parts = []
    if retrieved:
        excerpt_text = "\n\n".join(
            f"[Excerpt {i+1} | {r.get('law_name', '')} {r.get('article_no', '')}]: {r.get('text', '')[:400]}"
            for i, r in enumerate(retrieved[:5])
            if r.get("text")
        )
        if excerpt_text:
            context_parts.append(f"Reference provisions and excerpts:\n{excerpt_text}")

    context_block = ("\n\n---\nKnowledge Base Context:\n" + "\n\n".join(context_parts)) if context_parts else ""
    full_prompt = (
        f"Legal question: {query}"
        f"{context_block}\n\n"
        f"Please provide a comprehensive, detailed legal analysis."
    )

    chat_history = []
    for msg in history[-10:]:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [msg["content"]]})

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={"temperature": 0.15, "max_output_tokens": 4096, "top_p": 0.9},
        )
        chat = model.start_chat(history=chat_history)
        loop = asyncio.get_event_loop()
        response_iter = await loop.run_in_executor(
            None, lambda: chat.send_message(full_prompt, stream=True)
        )
        for chunk in response_iter:
            if chunk.text:
                yield f"data: {json.dumps({'token': chunk.text})}\n\n"
                await asyncio.sleep(0)
    except Exception as e:
        yield f"data: {json.dumps({'token': f'[Error: {str(e)}]'})}\n\n"

    citations = [
        {
            "node_id": r.get("id", ""),
            "type": r.get("source", "Statute"),
            "title": r.get("law_name", ""),
            "article": r.get("article_no", ""),
            "url": None,
        }
        for r in retrieved[:5]
        if r.get("law_name") or r.get("article_no")
    ]
    yield f"data: {json.dumps({'done': True, 'citations': citations, 'route_used': route, 'adapter_mode': 'non_thinking'})}\n\n"


@router.get("/chat/classify")
async def classify_query(q: str, jurisdiction: str = "JP"):
    """Classify a query via the Self-Route router (for debugging/testing)."""
    result = route_query(q, jurisdiction)
    return result.to_dict()


@router.post("/chat")
async def chat(request: ChatRequest):
    if request.model_name == "gemini":
        stream_gen = _gemini_stream(request.query, request.jurisdiction, request.history)
    else:
        stream_gen = _ollama_stream(
            request.query, request.jurisdiction, request.history, request.model_name,
            force_route=request.force_route,
        )
    return StreamingResponse(
        stream_gen,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
