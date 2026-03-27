"""Unified LLM factory — Qwen3 Swallow 8B (Ollama) as primary.

All client document processing must use local inference (守秘義務).
Gemini is available as an explicit opt-in for non-confidential tasks only.

Usage:
    from models.model_factory import get_llm
    llm = get_llm("You are a lawyer.")                        # Ollama (default)
    llm = get_llm("You are a lawyer.", model="ollama")        # Ollama explicit
    llm = get_llm("You are a lawyer.", thinking=True)         # Ollama + thinking mode
    llm = get_llm("You are a lawyer.", model="fine_tuned")    # fine-tuned adapter
    llm = get_llm("You are a lawyer.", model="gemini")        # Gemini (non-confidential only)
"""

import os

_VALID_MODELS = {"ollama", "llama", "fine_tuned", "jp_adapter", "us_adapter", "gemini"}
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "ollama")


def get_llm(
    system_prompt: str = "You are a legal expert in JP/US law.",
    model: str | None = None,
    thinking: bool = False,
):
    """Get a LangChain-compatible LLM instance.

    Args:
        system_prompt: System instruction for the LLM.
        model: "ollama" | "llama" | "fine_tuned" | "gemini"
               Defaults to DEFAULT_LLM_MODEL env var (default: "ollama").
        thinking: Enable Qwen3 Swallow Thinking mode (ignored for Gemini).
                  Use True for agents and complex graph_rag queries.
    """
    selected = (model or DEFAULT_MODEL).lower()
    if selected not in _VALID_MODELS:
        selected = "ollama"

    if selected == "gemini":
        from models.gemini_lc import get_llm as _gemini
        return _gemini(system_prompt)

    if selected in ("jp_adapter", "us_adapter"):
        from models.adapter_router import get_adapter_llm
        jurisdiction = "JP" if selected == "jp_adapter" else "US"
        return get_adapter_llm(jurisdiction, system_prompt=system_prompt, thinking=thinking)

    # "ollama" and "llama" both route to the local Ollama server
    from models.llama_lc import get_llama_llm
    return get_llama_llm(
        system_prompt=system_prompt,
        use_fine_tuned=(selected == "fine_tuned"),
        thinking=thinking,
    )


def get_available_models() -> list[dict]:
    """Return list of available model options with availability status."""
    from models.llama_lc import is_ollama_available, list_available_models, OLLAMA_MODEL, FINE_TUNED_MODEL
    from models.adapter_router import adapter_status, JP_ADAPTER_MODEL, US_ADAPTER_MODEL

    ollama_up = is_ollama_available()
    ollama_models = list_available_models() if ollama_up else []
    ollama_names = {m["name"].split(":")[0] for m in ollama_models}
    adapters = adapter_status()

    models = [
        {
            "id": "ollama",
            "name": f"Qwen3 Swallow ({OLLAMA_MODEL})",
            "type": "local",
            "available": ollama_up and any(OLLAMA_MODEL.split(":")[0] in n for n in ollama_names),
            "note": "Primary — confidentiality-compliant",
        },
        {
            "id": "fine_tuned",
            "name": "LexGraph Legal (fine-tuned adapter)",
            "type": "local",
            "available": ollama_up and any(FINE_TUNED_MODEL.split(":")[0] in n for n in ollama_names),
            "note": "Phase 4 — requires trained adapter",
        },
        {
            "id": "jp_adapter",
            "name": f"LexGraph JP ({JP_ADAPTER_MODEL})",
            "type": "local",
            "available": adapters["jp_adapter"]["available"],
            "note": "JP legal domain adapter — 会社法/金商法/民法",
        },
        {
            "id": "us_adapter",
            "name": f"LexGraph US ({US_ADAPTER_MODEL})",
            "type": "local",
            "available": adapters["us_adapter"]["available"],
            "note": "US legal domain adapter — DGCL/Securities/M&A",
        },
        {
            "id": "gemini",
            "name": "Gemini 2.5 Flash",
            "type": "cloud",
            "available": bool(os.getenv("GEMINI_API_KEY")),
            "note": "Non-confidential data only",
        },
    ]
    return models
