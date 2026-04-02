"""adapter_router — auto-selects the right LoRA adapter based on jurisdiction (RDD §13).

Two fine-tuned Ollama models are supported:
  JP adapter  — fine-tuned on JP legal QA (会社法, 金商法, 民法, 判例)
  US adapter  — fine-tuned on US legal QA (DGCL, Securities, M&A)

Model names are configurable via env vars:
  JP_ADAPTER_MODEL   default: lexgraph-legal-jp:latest
  US_ADAPTER_MODEL   default: lexgraph-legal-us:latest

Falls back to base Qwen3 Swallow model when adapters are unavailable.

Usage:
    from models.adapter_router import get_adapter_llm, adapter_status
    llm = get_adapter_llm("JP", system_prompt="...")    # JP adapter (or base fallback)
    llm = get_adapter_llm("US", system_prompt="...")    # US adapter (or base fallback)
    llm = get_adapter_llm("JP+US", system_prompt="...") # JP adapter for mixed jurisdiction
"""

import os
from functools import lru_cache

from models.llama_lc import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    is_ollama_available,
    list_available_models,
)

JP_ADAPTER_MODEL = os.getenv("JP_ADAPTER_MODEL", "lexgraph-legal-jp:latest")
US_ADAPTER_MODEL = os.getenv("US_ADAPTER_MODEL", "lexgraph-legal-us:latest")

# Legacy path-based config — kept for peft-based local loading (Phase 4 alternative)
ADAPTER_JP_PATH = os.getenv("ADAPTER_JP_PATH", "./adapters/adapter_jp")
ADAPTER_US_PATH = os.getenv("ADAPTER_US_PATH", "./adapters/adapter_us")


@lru_cache(maxsize=1)
def _available_model_names() -> frozenset:
    """Cached set of available Ollama model base names (before ':')."""
    models = list_available_models()
    return frozenset(m["name"].split(":")[0] for m in models)


def _model_available(model_name: str) -> bool:
    base = model_name.split(":")[0]
    return base in _available_model_names()


def select_adapter(jurisdiction: str) -> str:
    """Return the adapter identifier ('jp' or 'us') for a jurisdiction string.

    Kept for backwards compatibility with existing call sites.
    """
    return "jp" if (jurisdiction or "").upper() in ("JP", "JP+US") else "us"


def _resolve_ollama_model(jurisdiction: str) -> tuple[str, str]:
    """Return (ollama_model_name, adapter_type) for the given jurisdiction.

    adapter_type is one of: "jp_adapter" | "us_adapter" | "base"
    """
    jur = (jurisdiction or "").upper()

    if jur in ("JP", "JP+US"):
        if _model_available(JP_ADAPTER_MODEL):
            return JP_ADAPTER_MODEL, "jp_adapter"
    elif jur == "US":
        if _model_available(US_ADAPTER_MODEL):
            return US_ADAPTER_MODEL, "us_adapter"

    return OLLAMA_MODEL, "base"


def get_adapter_llm(
    jurisdiction: str,
    system_prompt: str = "You are a legal expert in JP/US law.",
    thinking: bool = False,
):
    """Return a ChatOllama instance using the best adapter for the given jurisdiction.

    Automatically falls back to the base model when adapters are unavailable.

    Args:
        jurisdiction: "JP" | "US" | "JP+US"
        system_prompt: System instruction for the model.
        thinking:      Enable Qwen3 Thinking mode.

    Returns:
        ChatOllama with ._adapter_type and ._thinking attributes set.

    Raises:
        RuntimeError: If Ollama server is not running.
    """
    if not is_ollama_available():
        raise RuntimeError(
            "Ollama is not running. Start with: ollama serve\n"
            "Client documents must not leave this machine (守秘義務)."
        )

    model_name, adapter_type = _resolve_ollama_model(jurisdiction)

    from langchain_ollama import ChatOllama

    llm = ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.1,
        num_ctx=4096,
        num_predict=1024,
        repeat_penalty=1.15,
        top_k=40,
        top_p=0.9,
        reasoning=False,
    )
    llm._thinking = thinking          # type: ignore[attr-defined]
    llm._adapter_type = adapter_type  # type: ignore[attr-defined]
    return llm


def invalidate_cache() -> None:
    """Clear the cached model-name list (call after pulling new Ollama models)."""
    _available_model_names.cache_clear()


def adapter_status() -> dict:
    """Return availability status for JP/US adapters and base model."""
    ollama_up = is_ollama_available()
    if not ollama_up:
        return {
            "ollama": False,
            "jp_adapter": {"model": JP_ADAPTER_MODEL, "available": False},
            "us_adapter": {"model": US_ADAPTER_MODEL, "available": False},
            "base": {"model": OLLAMA_MODEL, "available": False},
        }

    return {
        "ollama": True,
        "jp_adapter": {
            "model": JP_ADAPTER_MODEL,
            "available": _model_available(JP_ADAPTER_MODEL),
        },
        "us_adapter": {
            "model": US_ADAPTER_MODEL,
            "available": _model_available(US_ADAPTER_MODEL),
        },
        "base": {
            "model": OLLAMA_MODEL,
            "available": _model_available(OLLAMA_MODEL),
        },
    }
