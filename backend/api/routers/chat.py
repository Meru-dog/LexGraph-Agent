"""POST /chat — Graph RAG legal QA with SSE streaming via Gemini."""

import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tools.jurisdiction_router import jurisdiction_router
from tools.graph_search import graph_search
from tools.vector_search import vector_search

router = APIRouter(tags=["chat"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

JP_SYSTEM = (
    "You are a bilingual legal expert specializing in Japanese corporate and securities law "
    "(会社法, 金融商品取引法, 民法). Answer with precise statutory citations (article numbers). "
    "Use both Japanese legal terminology and English equivalents. Be concise and authoritative."
)

US_SYSTEM = (
    "You are a legal expert specializing in US corporate and securities law "
    "(Delaware GCL, Securities Exchange Act 1934, UCC). "
    "Answer with precise case and statutory citations. Be concise and authoritative."
)


class ChatRequest(BaseModel):
    query: str
    jurisdiction: str = "auto"
    session_id: str = ""
    history: list[dict] = []


async def _gemini_stream(query: str, jurisdiction: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Stream Gemini response tokens as SSE events."""
    detected_jur = jurisdiction if jurisdiction != "auto" else jurisdiction_router(query)
    system = JP_SYSTEM if detected_jur == "JP" else US_SYSTEM

    # Retrieve graph context (stub — live in Phase 3)
    graph_ctx = graph_search(query, detected_jur, ["Statute", "Case", "LegalConcept"])
    chunks = vector_search(query, detected_jur, top_k=3)

    # Build grounding context from graph results
    graph_context = ""
    if graph_ctx.get("nodes"):
        graph_context = "\n\nRelevant graph nodes:\n" + "\n".join(
            f"- {n.get('title', n.get('name', ''))} ({n.get('type', '')})"
            for n in graph_ctx["nodes"][:5]
        )

    full_prompt = query + graph_context

    # Build chat history for Gemini
    chat_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [msg["content"]]})

    try:
        import google.generativeai as genai  # noqa: PLC0415
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={"temperature": 0.1, "max_output_tokens": 1500},
        )

        chat = model.start_chat(history=chat_history)

        loop = asyncio.get_event_loop()
        response_iter = await loop.run_in_executor(
            None, lambda: chat.send_message(full_prompt, stream=True)
        )

        for chunk in response_iter:
            if chunk.text:
                yield f"data: {json.dumps({'token': chunk.text})}\n\n"
                await asyncio.sleep(0)  # yield control back to event loop

    except Exception as e:
        # Graceful degradation — stream an error token
        yield f"data: {json.dumps({'token': f'[Error: {str(e)}]'})}\n\n"

    # Final done event with citations
    citations = [
        {"node_id": n.get("node_id", ""), "type": n.get("type", "Statute"),
         "title": n.get("title", ""), "article": n.get("article_no", ""), "url": None}
        for n in graph_ctx.get("nodes", [])[:3]
    ]
    yield f"data: {json.dumps({'done': True, 'citations': citations, 'adapter_used': detected_jur.lower()})}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        _gemini_stream(request.query, request.jurisdiction, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
