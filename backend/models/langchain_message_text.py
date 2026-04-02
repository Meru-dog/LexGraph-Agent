"""Normalize LangChain message bodies to a single string (Ollama / multi-block content)."""

from __future__ import annotations

from typing import Any


def extract_message_text(message: Any) -> str:
    """Return user-visible text from an AIMessage (or similar).

    Handles:
    - str ``content`` (usual case)
    - list of str / OpenAI-style ``{"type":"text","text":...}`` blocks
    - empty main body with ``additional_kwargs["reasoning_content"]`` (Ollama thinking models)
    """
    content = getattr(message, "content", None)

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                if block.get("type") == "text" and "text" in block:
                    parts.append(str(block["text"]))
                elif "text" in block:
                    parts.append(str(block["text"]))
            else:
                parts.append(str(block))
        text = "".join(parts)
    elif content is None:
        text = ""
    else:
        text = str(content)

    text = (text or "").strip()
    kwargs = getattr(message, "additional_kwargs", None) or {}
    rc = kwargs.get("reasoning_content")
    if isinstance(rc, str) and rc.strip() and not text:
        return rc.strip()
    return text
