"""Tests for models.adapter_router — jurisdiction-based adapter selection."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.adapter_router import (
    select_adapter,
    _resolve_ollama_model,
    invalidate_cache,
    adapter_status,
    JP_ADAPTER_MODEL,
    US_ADAPTER_MODEL,
)


# ── select_adapter ───────────────────────────────────────────────────────────


class TestSelectAdapter:
    def test_jp_returns_jp(self):
        assert select_adapter("JP") == "jp"

    def test_us_returns_us(self):
        assert select_adapter("US") == "us"

    def test_jp_us_returns_jp(self):
        assert select_adapter("JP+US") == "jp"

    def test_lowercase(self):
        assert select_adapter("jp") == "jp"

    def test_empty_returns_us(self):
        assert select_adapter("") == "us"

    def test_none_returns_us(self):
        assert select_adapter(None) == "us"


# ── _resolve_ollama_model ────────────────────────────────────────────────────


class TestResolveOllamaModel:
    @patch("models.adapter_router._available_model_names")
    def test_jp_adapter_available(self, mock_names):
        mock_names.return_value = frozenset(["lexgraph-legal-jp", "qwen3-swallow"])
        invalidate_cache()
        model, adapter_type = _resolve_ollama_model("JP")
        assert adapter_type == "jp_adapter"
        assert "jp" in model.lower()

    @patch("models.adapter_router._available_model_names")
    def test_us_adapter_available(self, mock_names):
        mock_names.return_value = frozenset(["lexgraph-legal-us", "qwen3-swallow"])
        invalidate_cache()
        model, adapter_type = _resolve_ollama_model("US")
        assert adapter_type == "us_adapter"

    @patch("models.adapter_router._available_model_names")
    def test_fallback_to_base(self, mock_names):
        mock_names.return_value = frozenset(["qwen3-swallow"])
        invalidate_cache()
        model, adapter_type = _resolve_ollama_model("JP")
        assert adapter_type == "base"

    @patch("models.adapter_router._available_model_names")
    def test_jp_us_uses_jp(self, mock_names):
        mock_names.return_value = frozenset(["lexgraph-legal-jp", "lexgraph-legal-us"])
        invalidate_cache()
        _, adapter_type = _resolve_ollama_model("JP+US")
        assert adapter_type == "jp_adapter"

    @patch("models.adapter_router._available_model_names")
    def test_empty_jurisdiction_falls_to_base(self, mock_names):
        mock_names.return_value = frozenset(["lexgraph-legal-jp"])
        invalidate_cache()
        _, adapter_type = _resolve_ollama_model("")
        assert adapter_type == "base"


# ── adapter_status ───────────────────────────────────────────────────────────


class TestAdapterStatus:
    @patch("models.adapter_router.is_ollama_available", return_value=False)
    def test_ollama_down(self, mock_ollama):
        status = adapter_status()
        assert status["ollama"] is False
        assert status["jp_adapter"]["available"] is False
        assert status["us_adapter"]["available"] is False

    @patch("models.adapter_router._model_available", return_value=True)
    @patch("models.adapter_router.is_ollama_available", return_value=True)
    def test_ollama_up_all_available(self, mock_ollama, mock_model):
        status = adapter_status()
        assert status["ollama"] is True
        assert status["jp_adapter"]["available"] is True
        assert status["us_adapter"]["available"] is True
        assert status["base"]["available"] is True

    @patch("models.adapter_router.is_ollama_available", return_value=True)
    def test_status_has_model_names(self, mock_ollama):
        with patch("models.adapter_router._model_available", return_value=False):
            status = adapter_status()
        assert status["jp_adapter"]["model"] == JP_ADAPTER_MODEL
        assert status["us_adapter"]["model"] == US_ADAPTER_MODEL


# ── invalidate_cache ─────────────────────────────────────────────────────────


class TestInvalidateCache:
    def test_no_error(self):
        invalidate_cache()  # Should not raise
