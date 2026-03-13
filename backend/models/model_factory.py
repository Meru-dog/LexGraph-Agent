"""Unified LLM factory — select between Gemini and Llama/Ollama.

Usage:
    from models.model_factory import get_llm
    llm = get_llm("You are a lawyer.", model="gemini")
    llm = get_llm("You are a lawyer.", model="llama")
    llm = get_llm("You are a lawyer.", model="fine_tuned")
"""

import os


_VALID_MODELS = {"gemini", "llama", "fine_tuned"}
DEFAULT_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gemini")


def get_llm(system_prompt: str = "You are a legal expert in JP/US law.", model: str | None = None):
    """Get a LangChain-compatible LLM instance.

    Args:
        system_prompt: System instruction for the LLM
        model: "gemini" | "llama" | "fine_tuned" (defaults to DEFAULT_LLM_MODEL env or "gemini")
    """
    selected = (model or DEFAULT_MODEL).lower()
    if selected not in _VALID_MODELS:
        selected = "gemini"

    if selected == "gemini":
        from models.gemini_lc import get_llm as _gemini
        return _gemini(system_prompt)
    elif selected in ("llama", "fine_tuned"):
        from models.llama_lc import get_llama_llm
        return get_llama_llm(system_prompt, use_fine_tuned=(selected == "fine_tuned"))
    # Fallback
    from models.gemini_lc import get_llm as _gemini
    return _gemini(system_prompt)


def get_available_models() -> list[dict]:
    """Return list of available model options including local Ollama models."""
    models = [
        {"id": "gemini", "name": "Gemini 2.5 Flash", "type": "cloud", "available": True},
    ]
    try:
        from models.llama_lc import is_ollama_available, list_available_models, LLAMA_MODEL, FINE_TUNED_MODEL
        ollama_up = is_ollama_available()
        ollama_models = list_available_models() if ollama_up else []
        ollama_names = {m["name"].split(":")[0] for m in ollama_models}
        models.append({
            "id": "llama",
            "name": f"Llama ({LLAMA_MODEL})",
            "type": "local",
            "available": ollama_up and any(LLAMA_MODEL.split(":")[0] in n for n in ollama_names),
        })
        models.append({
            "id": "fine_tuned",
            "name": "LexGraph Legal (fine-tuned)",
            "type": "local",
            "available": ollama_up and any(FINE_TUNED_MODEL.split(":")[0] in n for n in ollama_names),
        })
    except Exception:
        pass
    return models
