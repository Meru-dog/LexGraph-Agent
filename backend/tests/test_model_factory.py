"""Tests for models.model_factory — unified LLM factory routing."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.model_factory import get_llm, _VALID_MODELS, DEFAULT_MODEL


# ── Model ID validation ─────────────────────────────────────────────────────


class TestValidModels:
    def test_valid_model_set(self):
        expected = {"ollama", "llama", "fine_tuned", "jp_adapter", "us_adapter", "gemini"}
        assert _VALID_MODELS == expected

    def test_default_model(self):
        assert DEFAULT_MODEL in _VALID_MODELS or DEFAULT_MODEL == "ollama"


# ── get_llm routing ─────────────────────────────────────────────────────────


class TestGetLLM:
    @patch("models.model_factory.get_llm.__module__", "models.model_factory")
    @patch("models.llama_lc.get_llama_llm")
    def test_ollama_route(self, mock_llama):
        mock_llama.return_value = MagicMock()
        llm = get_llm("You are a lawyer.", model="ollama")
        mock_llama.assert_called_once_with(
            system_prompt="You are a lawyer.",
            use_fine_tuned=False,
            thinking=False,
        )

    @patch("models.llama_lc.get_llama_llm")
    def test_llama_routes_to_ollama(self, mock_llama):
        mock_llama.return_value = MagicMock()
        get_llm("prompt", model="llama")
        mock_llama.assert_called_once()

    @patch("models.llama_lc.get_llama_llm")
    def test_fine_tuned_route(self, mock_llama):
        mock_llama.return_value = MagicMock()
        get_llm("prompt", model="fine_tuned")
        mock_llama.assert_called_once_with(
            system_prompt="prompt",
            use_fine_tuned=True,
            thinking=False,
        )

    @patch("models.adapter_router.get_adapter_llm")
    def test_jp_adapter_route(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        get_llm("prompt", model="jp_adapter")
        mock_adapter.assert_called_once_with("JP", system_prompt="prompt", thinking=False)

    @patch("models.adapter_router.get_adapter_llm")
    def test_us_adapter_route(self, mock_adapter):
        mock_adapter.return_value = MagicMock()
        get_llm("prompt", model="us_adapter")
        mock_adapter.assert_called_once_with("US", system_prompt="prompt", thinking=False)

    @patch("models.llama_lc.get_llama_llm")
    def test_invalid_model_falls_to_ollama(self, mock_llama):
        mock_llama.return_value = MagicMock()
        get_llm("prompt", model="invalid_model_xyz")
        mock_llama.assert_called_once()

    @patch("models.llama_lc.get_llama_llm")
    def test_none_model_uses_default(self, mock_llama):
        mock_llama.return_value = MagicMock()
        get_llm("prompt", model=None)
        mock_llama.assert_called_once()

    @patch("models.llama_lc.get_llama_llm")
    def test_thinking_passed_through(self, mock_llama):
        mock_llama.return_value = MagicMock()
        get_llm("prompt", model="ollama", thinking=True)
        mock_llama.assert_called_once_with(
            system_prompt="prompt",
            use_fine_tuned=False,
            thinking=True,
        )

    @patch("models.gemini_lc.get_llm")
    def test_gemini_route(self, mock_gemini):
        mock_gemini.return_value = MagicMock()
        get_llm("prompt", model="gemini")
        mock_gemini.assert_called_once_with("prompt")
