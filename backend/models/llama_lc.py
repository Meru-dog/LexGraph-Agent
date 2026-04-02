"""Ollama local LLM wrapper — Qwen3 Swallow 8B RL as primary model.

Primary model: qwen3-swallow:8b (Tokyo Institute of Technology + AIST)
  - Japanese SoTA among 8B-class open LLMs (as of 2026-02)
  - Apache 2.0 license, runs fully local via Ollama
  - Supports Thinking mode (/think) and Non-thinking mode (/no_think)

Confidentiality: client documents MUST NOT leave this machine.
  All inference runs locally. No external API fallback for client data.

Setup:
  brew install ollama
  ollama pull qwen3-swallow:8b
  ollama serve

Env vars:
  OLLAMA_BASE_URL    default: http://localhost:11434
  OLLAMA_MODEL       default: qwen3-swallow:8b
  FINE_TUNED_MODEL   default: lexgraph-legal:latest
"""

import os

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-swallow:8b")
FINE_TUNED_MODEL = os.getenv("FINE_TUNED_MODEL", "lexgraph-legal:latest")

# Legacy alias — kept for backwards compatibility with model_factory references
LLAMA_MODEL = OLLAMA_MODEL


def _pick_existing_ollama_model(preferred: str) -> str:
    """Return a runnable Ollama model name, falling back when preferred is missing.

    Some environments return HTTP 404 on /api/chat when the requested model tag does
    not exist locally. To avoid hard failure from a stale default in .env, we choose:
      1) preferred model if installed
      2) first installed model from a short priority list
      3) first model returned by /api/tags
    """
    models = list_available_models()
    if not models:
        return preferred

    installed = [m["name"] for m in models if m.get("name")]
    installed_set = set(installed)
    preferred_base = preferred.split(":")[0]

    # Exact tag match first, then base-name match (e.g. qwen3-swallow:*).
    if preferred in installed_set:
        return preferred
    for name in installed:
        if name.split(":")[0] == preferred_base:
            return name

    priority = [
        "qwen3-swallow:8b",
        "qwen2.5:7b",
        "llama3.1:8b",
        "llama3.2:3b",
    ]
    for candidate in priority:
        if candidate in installed_set:
            print(
                f"[ollama] configured model '{preferred}' not found; "
                f"falling back to '{candidate}'."
            )
            return candidate

    fallback = installed[0]
    print(
        f"[ollama] configured model '{preferred}' not found; "
        f"falling back to installed model '{fallback}'."
    )
    return fallback


def is_ollama_available() -> bool:
    """Check if Ollama server is running."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def get_llama_llm(
    system_prompt: str = "",   # Ignored — pass SystemMessage in the messages list
    use_fine_tuned: bool = False,
    thinking: bool = False,
):
    """Return a ChatOllama LangChain instance for the local Qwen3 Swallow model.

    Args:
        system_prompt: System instruction for the model.
        use_fine_tuned: Use the fine-tuned adapter instead of the base model.
        thinking: Enable Thinking mode (slower, higher accuracy — for agents and
                  complex graph_rag queries). Non-thinking mode is used for simple QA.

    Raises:
        RuntimeError: If Ollama is not running. No cloud fallback — confidentiality.
    """
    if not is_ollama_available():
        raise RuntimeError(
            "Ollama is not running. Start it with: ollama serve\n"
            "Client documents must not be sent to external APIs (守秘義務)."
        )

    from langchain_ollama import ChatOllama

    requested_model = FINE_TUNED_MODEL if use_fine_tuned else OLLAMA_MODEL
    model_name = _pick_existing_ollama_model(requested_model)

    # Thinking mode appends /think to user messages at invocation time.
    # Stored on the instance so callers can inspect it.
    # reasoning=False: avoid Ollama splitting answer into reasoning_content with empty
    # main body (common with Qwen3 / Swallow on some Ollama builds). We use /think
    # suffix via apply_thinking_mode in chat when needed.
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
    # Attach thinking flag for use by _apply_thinking_mode helper
    llm._thinking = thinking  # type: ignore[attr-defined]
    return llm


def apply_thinking_mode(messages: list, thinking: bool) -> list:
    """Append /think or /no_think suffix to the last HumanMessage content.

    Qwen3 Swallow activates its chain-of-thought reasoning when the user
    message ends with ' /think'. Non-thinking mode uses ' /no_think'.
    """
    from langchain_core.messages import HumanMessage

    if not messages:
        return messages

    result = list(messages)
    last = result[-1]
    if isinstance(last, HumanMessage):
        suffix = " /think" if thinking else " /no_think"
        result[-1] = HumanMessage(content=last.content + suffix)
    return result


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
