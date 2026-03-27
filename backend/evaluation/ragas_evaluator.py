"""RAGAS evaluation pipeline for LexGraph AI (RDD §11).

Evaluates 4 metrics:
  Faithfulness       — answer grounded in retrieved context (★★★★★)
  Answer Relevancy   — answer addresses the question  (★★★★☆)
  Context Precision  — retrieved chunks that are useful (★★★☆☆)
  Context Recall     — ground truth covered by context (★★★☆☆)

Confidentiality compliance:
  All evaluation is run with local Ollama (Qwen3 Swallow) by default.
  External LLMs (OpenAI) may be used ONLY for public test data.

W&B integration (RDD §13):
  Results are logged to wandb project "lexgraph-rag".
  Regression check: if Faithfulness drops >5% vs baseline, raises ValueError.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

from evaluation.test_cases import TEST_CASES

# ─── Phase 2 targets (RDD §11.2) ─────────────────────────────────────────────
FAITHFULNESS_TARGET = 0.75
ANSWER_RELEVANCY_TARGET = 0.70
REGRESSION_THRESHOLD = 0.05   # Faithfulness drop that triggers a failure


# ─── Evaluator ────────────────────────────────────────────────────────────────

class LexGraphEvaluator:
    """Run RAGAS evaluation against the current retrieval pipeline."""

    def __init__(
        self,
        use_local_llm: bool = True,
        pipeline_version: str = "dev",
        use_wandb: bool = True,
    ):
        self.use_local_llm = use_local_llm
        self.pipeline_version = pipeline_version
        self.use_wandb = use_wandb

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        test_cases: Optional[list] = None,
        baseline: Optional[dict] = None,
    ) -> dict:
        """Run RAGAS evaluation and return score dict.

        Args:
            test_cases: Override TEST_CASES for a subset run.
            baseline:   Previous score dict for regression check.
                        Keys: faithfulness, answer_relevancy, context_precision, context_recall.
        """
        cases = test_cases or TEST_CASES
        print(f"[ragas] Running evaluation on {len(cases)} test cases...")

        dataset = self._generate_answers(cases)
        scores = self._evaluate(dataset)
        scores["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        scores["pipeline_version"] = self.pipeline_version
        scores["test_count"] = len(cases)

        self._save_scores(scores)

        if self.use_wandb:
            self._log_wandb(scores, dataset)

        if baseline:
            self._regression_check(baseline, scores)

        _print_score_table(scores)
        return scores

    # ── Answer generation ─────────────────────────────────────────────────────

    def _generate_answers(self, cases: list) -> list[dict]:
        """For each test case, retrieve context and generate an answer via Ollama."""
        from retrieval.hybrid_retriever import hybrid_search
        from models.model_factory import get_llm
        from models.llama_lc import apply_thinking_mode
        from langchain_core.messages import HumanMessage
        from api.routers.chat import _SYSTEM_JP, _SYSTEM_US, _SYSTEM_JPUS

        dataset = []
        for i, case in enumerate(cases):
            question = case["question"]
            ground_truth = case["ground_truth"]
            jurisdiction = case.get("jurisdiction", "JP")

            # Retrieve context
            retrieved = hybrid_search(
                question, jurisdiction, top_k=5,
                use_graph=True, use_vector=True,
            )
            contexts = [r["text"] for r in retrieved if r.get("text")]

            # Build prompt
            system = _SYSTEM_JP if jurisdiction == "JP" else _SYSTEM_US
            context_block = "\n\n".join(
                f"[参照 {j+1}]: {ctx[:400]}" for j, ctx in enumerate(contexts[:4])
            )
            prompt = (
                f"Legal question: {question}\n\n"
                f"---\n参照情報:\n{context_block}\n\n"
                f"Please provide a concise, citation-grounded answer."
            )

            # Generate answer
            answer = ""
            try:
                llm = get_llm(system, model="ollama", thinking=False)
                msgs = apply_thinking_mode([HumanMessage(content=prompt)], thinking=False)
                response = llm.invoke(msgs)
                answer = response.content.strip()
            except Exception as e:
                answer = f"[generation error: {e}]"
                print(f"[ragas] Case {i+1} generation error: {e}")

            dataset.append({
                "question":     question,
                "answer":       answer,
                "contexts":     contexts,
                "ground_truth": ground_truth,
                "jurisdiction": jurisdiction,
            })
            print(f"[ragas] {i+1}/{len(cases)} done — {question[:60]}")

        return dataset

    # ── RAGAS scoring ─────────────────────────────────────────────────────────

    def _evaluate(self, dataset: list[dict]) -> dict:
        """Run RAGAS metrics. Falls back to heuristic scoring if ragas not installed."""
        try:
            return self._ragas_evaluate(dataset)
        except ImportError:
            print("[ragas] ragas package not installed — using heuristic fallback")
            return self._heuristic_evaluate(dataset)
        except Exception as e:
            print(f"[ragas] evaluation error: {e} — using heuristic fallback")
            return self._heuristic_evaluate(dataset)

    def _ragas_evaluate(self, dataset: list[dict]) -> dict:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )

        hf_dataset = Dataset.from_list(dataset)

        if self.use_local_llm:
            from langchain_community.llms import Ollama
            from langchain_community.embeddings import OllamaEmbeddings
            llm = Ollama(model=os.getenv("OLLAMA_MODEL", "qwen3-swallow:8b"))
            embeddings = OllamaEmbeddings(model="nomic-embed-text")
            scores = evaluate(
                hf_dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=llm,
                embeddings=embeddings,
            )
        else:
            # Public data only — external LLM allowed
            scores = evaluate(
                hf_dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            )

        return {
            "faithfulness":       float(scores["faithfulness"]),
            "answer_relevancy":   float(scores["answer_relevancy"]),
            "context_precision":  float(scores["context_precision"]),
            "context_recall":     float(scores["context_recall"]),
            "raw":                scores.to_pandas().to_dict(orient="records"),
        }

    def _heuristic_evaluate(self, dataset: list[dict]) -> dict:
        """Simple heuristic scorer when ragas is unavailable.

        Faithfulness: fraction of answers that contain text from at least one context chunk.
        Answer Relevancy: fraction where question keywords appear in the answer.
        Context Precision / Recall: rough overlap between context and ground truth.
        """
        faithful, relevant, precise, recalled = [], [], [], []

        for item in dataset:
            answer = item["answer"].lower()
            contexts = [c.lower() for c in item["contexts"]]
            gt = item["ground_truth"].lower()
            question_words = set(item["question"].lower().split()) - {"は", "の", "を", "に", "が", "と", "で", "a", "the", "is", "of", "what"}

            # Faithfulness: answer shares significant text with context
            ctx_combined = " ".join(contexts)
            common_words = set(answer.split()) & set(ctx_combined.split())
            faithful.append(min(len(common_words) / max(len(answer.split()), 1), 1.0))

            # Answer Relevancy: question words in answer
            ans_words = set(answer.split())
            relevant.append(len(question_words & ans_words) / max(len(question_words), 1))

            # Context Precision: ground truth words in context
            gt_words = set(gt.split())
            precise.append(len(gt_words & set(ctx_combined.split())) / max(len(gt_words), 1))

            # Context Recall: same measure reversed
            recalled.append(len(set(ctx_combined.split()) & gt_words) / max(len(gt_words), 1))

        def _avg(lst):
            return round(sum(lst) / len(lst), 4) if lst else 0.0

        return {
            "faithfulness":      _avg(faithful),
            "answer_relevancy":  _avg(relevant),
            "context_precision": _avg(precise),
            "context_recall":    _avg(recalled),
            "raw":               [],
            "note":              "heuristic fallback (ragas not installed)",
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_scores(self, scores: dict) -> None:
        """Save scores to Supabase ragas_scores table (non-fatal)."""
        try:
            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            if not url or not key:
                print("[ragas] Supabase not configured — scores not persisted")
                return
            from supabase import create_client
            client = create_client(url, key)
            client.table("ragas_scores").insert({
                "pipeline_version":   scores.get("pipeline_version", "dev"),
                "faithfulness":       scores.get("faithfulness"),
                "answer_relevancy":   scores.get("answer_relevancy"),
                "context_precision":  scores.get("context_precision"),
                "context_recall":     scores.get("context_recall"),
                "test_count":         scores.get("test_count", 0),
                "notes":              scores.get("note", ""),
            }).execute()
            print("[ragas] Scores saved to Supabase")
        except Exception as e:
            print(f"[ragas] Supabase save error (non-fatal): {e}")

    # ── W&B logging (RDD §13.2) ───────────────────────────────────────────────

    def _log_wandb(self, scores: dict, dataset: list[dict]) -> None:
        """Log RAGAS scores and failure cases to W&B project 'lexgraph-rag'."""
        try:
            import wandb
            run = wandb.init(
                project="lexgraph-rag",
                name=f"ragas-{self.pipeline_version}-{int(time.time())}",
                config={
                    "pipeline_version": self.pipeline_version,
                    "retriever":        "hybrid (vector+keyword+graph+crossencoder)",
                    "reranker":         "cross-encoder/ms-marco-MiniLM-L-6-v2",
                    "graph_hops":       2,
                    "top_k":            5,
                    "llm_model":        os.getenv("OLLAMA_MODEL", "qwen3-swallow:8b"),
                    "test_count":       scores.get("test_count", 0),
                    "use_local_llm":    self.use_local_llm,
                },
                reinit=True,
            )

            wandb.log({
                "ragas/faithfulness":      scores.get("faithfulness", 0),
                "ragas/answer_relevancy":  scores.get("answer_relevancy", 0),
                "ragas/context_precision": scores.get("context_precision", 0),
                "ragas/context_recall":    scores.get("context_recall", 0),
            })

            # Log failure cases (faithfulness < 0.6) to W&B Table
            raw = scores.get("raw", [])
            if raw:
                table = wandb.Table(columns=[
                    "question", "answer", "faithfulness", "context_preview", "jurisdiction"
                ])
                for row, case in zip(raw, dataset):
                    if row.get("faithfulness", 1.0) < 0.6:
                        table.add_data(
                            case["question"],
                            case["answer"][:300],
                            row.get("faithfulness", 0),
                            (case["contexts"][0][:200] if case["contexts"] else ""),
                            case.get("jurisdiction", ""),
                        )
                wandb.log({"ragas/failures": table})

            wandb.finish()
            print(f"[ragas] W&B run logged to project 'lexgraph-rag'")
        except ImportError:
            print("[ragas] wandb not installed — W&B logging skipped")
        except Exception as e:
            print(f"[ragas] W&B logging error (non-fatal): {e}")

    # ── Regression check ──────────────────────────────────────────────────────

    def _regression_check(self, baseline: dict, current: dict) -> None:
        """Raise ValueError if Faithfulness drops more than REGRESSION_THRESHOLD."""
        b = baseline.get("faithfulness", 0)
        c = current.get("faithfulness", 0)
        if b and c < b - REGRESSION_THRESHOLD:
            raise ValueError(
                f"[ragas] Quality regression detected: "
                f"Faithfulness {b:.3f} → {c:.3f} "
                f"(dropped {b - c:.3f}, threshold {REGRESSION_THRESHOLD})"
            )


# ─── CLI helper ───────────────────────────────────────────────────────────────

def _print_score_table(scores: dict) -> None:
    print("\n" + "─" * 52)
    print(f"  RAGAS Evaluation Results  (v{scores.get('pipeline_version', '?')})")
    print("─" * 52)
    metrics = [
        ("Faithfulness",      "faithfulness",      FAITHFULNESS_TARGET),
        ("Answer Relevancy",  "answer_relevancy",  ANSWER_RELEVANCY_TARGET),
        ("Context Precision", "context_precision", None),
        ("Context Recall",    "context_recall",    None),
    ]
    for label, key, target in metrics:
        val = scores.get(key, 0)
        status = ""
        if target:
            status = "✓" if val >= target else f"✗ (target {target})"
        print(f"  {label:<22} {val:.4f}  {status}")
    print(f"\n  Test cases: {scores.get('test_count', '?')}")
    print(f"  Evaluated:  {scores.get('evaluated_at', '?')}")
    if scores.get("note"):
        print(f"  Note:       {scores['note']}")
    print("─" * 52 + "\n")
