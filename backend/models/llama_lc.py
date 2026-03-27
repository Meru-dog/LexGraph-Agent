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

    model_name = FINE_TUNED_MODEL if use_fine_tuned else OLLAMA_MODEL

    # Thinking mode appends /think to user messages at invocation time.
    # Stored on the instance so callers can inspect it.
    llm = ChatOllama(
        model=model_name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.1,
        num_ctx=4096,
        num_predict=1024,
        repeat_penalty=1.15,
        top_k=40,
        top_p=0.9,
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
