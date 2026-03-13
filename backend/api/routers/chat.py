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

_SYSTEM_JP = """You are a bilingual senior legal expert at a top-tier law firm specializing in Japanese corporate and securities law.

Expertise:
- 会社法 (Companies Act): corporate governance, directors' duties, shareholder rights, mergers
- 金融商品取引法 (FIEA): securities regulation, disclosure obligations, insider trading, TOB rules
- 民法 (Civil Code): contracts, torts, obligations, property rights
- 独占禁止法 (Antimonopoly Act): M&A competition clearance, cartel regulations
- 労働法 (Labor Law): employment contracts, dismissal rules, union relations

Response guidelines:
- Provide COMPREHENSIVE, DETAILED explanations — never truncate
- Always cite specific article numbers (e.g., 会社法第362条)
- Use both Japanese legal terms and English equivalents in parentheses
- Structure answers with numbered points or sections when explaining multiple concepts
- For complex questions, cover: (1) Applicable law, (2) Key requirements, (3) Practical implications, (4) Risks/exceptions
- Minimum 300 words for substantive legal questions
- If context from the knowledge graph is provided, integrate it into your analysis"""

_SYSTEM_US = """You are a senior legal expert at a top-tier US law firm specializing in corporate and securities law.

Expertise:
- Delaware General Corporation Law (DGCL): corporate governance, fiduciary duties, M&A
- Securities Act of 1933 & Exchange Act of 1934: disclosure, registration, Rule 10b-5, insider trading
- Dodd-Frank Act: financial regulation, whistleblower, derivatives
- UCC Articles 2, 9: commercial contracts, secured transactions
- ERISA, WARN Act, state employment law

Response guidelines:
- Provide COMPREHENSIVE, DETAILED explanations — never truncate
- Always cite specific sections (e.g., DGCL § 141(a), Rule 10b-5 under Exchange Act § 10(b))
- Reference key cases where relevant (e.g., Smith v. Van Gorkom, Revlon Inc. v. MacAndrews)
- Structure with numbered points for multi-part analysis
- For complex questions, cover: (1) Applicable law, (2) Key standards, (3) Case law, (4) Practical implications
- Minimum 300 words for substantive legal questions
- If context from the knowledge graph is provided, integrate it into your analysis"""

_SYSTEM_JPUS = """You are a bilingual senior legal expert specializing in JP/US dual-jurisdiction corporate law.

You seamlessly combine analysis of:
- Japanese law (会社法, 金融商品取引法, 民法) with precise article citations
- US law (DGCL, Securities Acts, UCC) with section and case citations
- Cross-border M&A, joint ventures, and regulatory clearances in both jurisdictions
- Comparative analysis of JP vs US legal frameworks

Response guidelines:
- Provide COMPREHENSIVE, DETAILED explanations covering BOTH jurisdictions
- Organize responses by jurisdiction (JP then US) or by topic (whichever is clearer)
- Always cite statutory references in both systems
- Minimum 400 words for questions touching both jurisdictions
- If context from the knowledge graph is provided, integrate it into your analysis"""


class ChatRequest(BaseModel):
    query: str
    jurisdiction: str = "auto"
    session_id: str = ""
    history: list[dict] = []


async def _gemini_stream(query: str, jurisdiction: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Stream Gemini response tokens as SSE events."""
    detected_jur = jurisdiction if jurisdiction != "auto" else jurisdiction_router(query)

    # Select system prompt based on jurisdiction
    if detected_jur == "JP":
        system = _SYSTEM_JP
    elif detected_jur == "US":
        system = _SYSTEM_US
    else:
        system = _SYSTEM_JPUS

    # Retrieve graph and vector context
    graph_ctx = graph_search(query, detected_jur, ["Statute", "Case", "LegalConcept", "Provision"])
    chunks = vector_search(query, detected_jur, top_k=5)

    # Build rich grounding context
    context_parts = []

    if graph_ctx.get("nodes"):
        node_lines = "\n".join(
            f"  - {n.get('title', n.get('name', ''))}: {n.get('article_no', '')} ({n.get('type', '')})"
            for n in graph_ctx["nodes"][:6]
        )
        context_parts.append(f"Relevant legal provisions from knowledge graph:\n{node_lines}")

    if chunks:
        chunk_texts = "\n\n".join(
            f"[Document excerpt {i+1}]: {c.get('text', '')[:400]}"
            for i, c in enumerate(chunks[:3])
            if c.get("text")
        )
        if chunk_texts:
            context_parts.append(f"Relevant document excerpts:\n{chunk_texts}")

    # Build the full prompt with context
    context_block = ("\n\n---\nKnowledge Base Context:\n" + "\n\n".join(context_parts)) if context_parts else ""
    full_prompt = (
        f"Legal question: {query}"
        f"{context_block}\n\n"
        f"Please provide a comprehensive, detailed legal analysis. "
        f"Structure your response clearly with sections if addressing multiple aspects."
    )

    # Build chat history
    chat_history = []
    for msg in history[-10:]:  # Last 10 messages for context
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [msg["content"]]})

    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config={
                "temperature": 0.15,
                "max_output_tokens": 4096,  # Increased from 1500
                "top_p": 0.9,
            },
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

    # Final done event with citations
    citations = [
        {
            "node_id": n.get("node_id", ""),
            "type": n.get("type", "Statute"),
            "title": n.get("title", ""),
            "article": n.get("article_no", ""),
            "url": None,
        }
        for n in graph_ctx.get("nodes", [])[:5]
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
