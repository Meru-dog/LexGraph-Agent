"""Tests for evaluation.ragas_evaluator — heuristic fallback scorer."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evaluation.ragas_evaluator import (
    LexGraphEvaluator,
    FAITHFULNESS_TARGET,
    ANSWER_RELEVANCY_TARGET,
    REGRESSION_THRESHOLD,
)


# ── Heuristic evaluator ─────────────────────────────────────────────────────


class TestHeuristicEvaluate:
    def setup_method(self):
        self.evaluator = LexGraphEvaluator(use_local_llm=True, use_wandb=False)

    def test_empty_dataset(self):
        scores = self.evaluator._heuristic_evaluate([])
        assert scores["faithfulness"] == 0.0
        assert scores["answer_relevancy"] == 0.0
        assert "heuristic" in scores.get("note", "")

    def test_perfect_overlap(self):
        dataset = [{
            "question": "What is the Companies Act?",
            "answer": "The Companies Act governs corporate law in Japan.",
            "contexts": ["The Companies Act governs corporate law in Japan."],
            "ground_truth": "The Companies Act governs corporate law in Japan.",
        }]
        scores = self.evaluator._heuristic_evaluate(dataset)
        assert scores["faithfulness"] > 0.5
        assert scores["context_precision"] > 0.5

    def test_no_overlap(self):
        dataset = [{
            "question": "What is X?",
            "answer": "Alpha beta gamma delta.",
            "contexts": ["Completely different content here."],
            "ground_truth": "Entirely unrelated ground truth text.",
        }]
        scores = self.evaluator._heuristic_evaluate(dataset)
        assert scores["faithfulness"] < 0.5

    def test_multiple_items(self):
        dataset = [
            {
                "question": "What is DGCL?",
                "answer": "DGCL is the Delaware General Corporation Law.",
                "contexts": ["DGCL is the Delaware General Corporation Law governing Delaware corps."],
                "ground_truth": "Delaware General Corporation Law.",
            },
            {
                "question": "会社法とは？",
                "answer": "会社法は日本の会社に関する法律です。",
                "contexts": ["会社法は日本の会社の設立や運営について定めた法律である。"],
                "ground_truth": "日本の会社に関する法律。",
            },
        ]
        scores = self.evaluator._heuristic_evaluate(dataset)
        assert 0 <= scores["faithfulness"] <= 1
        assert 0 <= scores["answer_relevancy"] <= 1
        assert 0 <= scores["context_precision"] <= 1
        assert 0 <= scores["context_recall"] <= 1

    def test_empty_contexts(self):
        dataset = [{
            "question": "What is X?",
            "answer": "X is something.",
            "contexts": [],
            "ground_truth": "X is something.",
        }]
        scores = self.evaluator._heuristic_evaluate(dataset)
        assert scores["faithfulness"] == 0.0

    def test_stop_words_excluded_from_relevancy(self):
        dataset = [{
            "question": "What is the definition of consideration?",
            "answer": "Consideration is a key element of contract law.",
            "contexts": ["Consideration means something of value exchanged."],
            "ground_truth": "Something of value exchanged in a contract.",
        }]
        scores = self.evaluator._heuristic_evaluate(dataset)
        assert isinstance(scores["answer_relevancy"], float)


# ── Regression check ─────────────────────────────────────────────────────────


class TestRegressionCheck:
    def setup_method(self):
        self.evaluator = LexGraphEvaluator(use_wandb=False)

    def test_no_regression(self):
        baseline = {"faithfulness": 0.80}
        current = {"faithfulness": 0.78}
        # Should not raise (drop = 0.02 < threshold 0.05)
        self.evaluator._regression_check(baseline, current)

    def test_regression_detected(self):
        baseline = {"faithfulness": 0.80}
        current = {"faithfulness": 0.70}
        with pytest.raises(ValueError, match="regression"):
            self.evaluator._regression_check(baseline, current)

    def test_exact_threshold_no_raise(self):
        baseline = {"faithfulness": 0.80}
        current = {"faithfulness": 0.75}
        # Drop = 0.05 = threshold, but condition is strict < (not <=)
        self.evaluator._regression_check(baseline, current)

    def test_improvement_no_raise(self):
        baseline = {"faithfulness": 0.70}
        current = {"faithfulness": 0.90}
        self.evaluator._regression_check(baseline, current)

    def test_zero_baseline_no_raise(self):
        baseline = {"faithfulness": 0}
        current = {"faithfulness": 0.50}
        self.evaluator._regression_check(baseline, current)


# ── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_faithfulness_target(self):
        assert FAITHFULNESS_TARGET == 0.75

    def test_answer_relevancy_target(self):
        assert ANSWER_RELEVANCY_TARGET == 0.70

    def test_regression_threshold(self):
        assert REGRESSION_THRESHOLD == 0.05
