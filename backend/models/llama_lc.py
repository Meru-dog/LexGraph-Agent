"""Llama LangChain wrapper via Ollama local server.

Ollama serves local LLMs including fine-tuned models (GGUF format).
Default model: llama3.1:8b (or lexgraph-legal:latest for fine-tuned version)

Setup:
  brew install ollama
  ollama pull llama3.1:8b
  # For fine-tuned: ollama create lexgraph-legal -f ./fine_tune/Modelfile
  ollama serve  (runs on http://localhost:11434 by default)

Env vars:
  OLLAMA_BASE_URL    default: http://localhost:11434
  LLAMA_MODEL        default: llama3.1:8b
  FINE_TUNED_MODEL   default: lexgraph-legal:latest
"""

import os
from functools import lru_cache

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "llama3.1:8b")
FINE_TUNED_MODEL = os.getenv("FINE_TUNED_MODEL", "lexgraph-legal:latest")


def is_ollama_available() -> bool:
    """Check if Ollama server is running."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


@lru_cache(maxsize=4)
def get_llama_llm(system_prompt: str = "You are a legal expert in JP/US law.", use_fine_tuned: bool = False):
    """Return a cached ChatOllama LangChain instance.

    Falls back to Gemini if Ollama is not available.
    """
    try:
        from langchain_community.chat_models import ChatOllama
        if not is_ollama_available():
            raise RuntimeError("Ollama not running")
        model_name = FINE_TUNED_MODEL if use_fine_tuned else LLAMA_MODEL
        return ChatOllama(
            model=model_name,
            base_url=OLLAMA_BASE_URL,
            temperature=0.1,
            num_predict=2048,
            system=system_prompt,
        )
    except Exception as e:
        print(f"[llama_lc] Ollama unavailable ({e}), falling back to Gemini")
        from models.gemini_lc import get_llm as get_gemini
        return get_gemini(system_prompt)


def list_available_models() -> list[dict]:
    """Return list of models available in Ollama."""
    import json, urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=3) as r:
            data = json.loads(r.read())
            return [
                {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
                for m in data.get("models", [])
            ]
    except Exception:
        return []
