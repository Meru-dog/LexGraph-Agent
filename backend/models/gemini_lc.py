"""Shared Gemini LangChain LLM instance for use in LangGraph agents."""

import os
from functools import lru_cache

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


@lru_cache(maxsize=2)
def get_llm(system_prompt: str = "You are a legal expert in JP/US law."):
    """Return a cached ChatGoogleGenerativeAI instance.

    Phase 2-3: Gemini.
    Phase 4:   Replace with LangChain vLLM wrapper pointing at fine-tuned LLaMA.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=os.environ["GEMINI_API_KEY"],
        temperature=0.1,
        max_output_tokens=2048,
        request_options={"timeout": 30},
    )
