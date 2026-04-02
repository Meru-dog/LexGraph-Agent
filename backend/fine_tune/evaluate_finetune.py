"""4-condition evaluation: Base/FT × RAG off/on with RAGAS + W&B.

Conditions (same eval dataset for all):
  A. base / no-rag
  B. base / rag
  C. finetuned / no-rag
  D. finetuned / rag

Usage:
    python fine_tune/evaluate_finetune.py \
        --base_model qwen2.5:1.5b \
        --finetuned_model lexgraph-legal \
        --eval_dataset ../eval_data/legal_eval_4way.json \
        --max_examples 8 \
        --ragas_timeout_sec 180 \
        --ragas_max_workers 1 \
        --version v2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
FAITHFULNESS_TARGET = 0.75
ANSWER_RELEVANCY_TARGET = 0.70


def _load_cases(eval_dataset: str | None, max_examples: int | None, seed: int) -> list[dict] | None:
    import random

    if not eval_dataset:
        return None
    p = Path(eval_dataset)
    if not p.exists():
        raise SystemExit(f"eval dataset not found: {p}")
    rows = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise SystemExit("eval dataset must be a non-empty JSON list")
    if max_examples and len(rows) > max_examples:
        random.Random(seed).shuffle(rows)
        rows = rows[:max_examples]
    return rows


def _eval_model(
    model_name: str,
    pipeline_version: str,
    use_rag: bool,
    cases: list[dict] | None,
    ragas_timeout_sec: int,
    ragas_max_workers: int,
) -> tuple[dict, list[dict]]:
    from evaluation.ragas_evaluator import LexGraphEvaluator

    prev_model = os.environ.get("OLLAMA_MODEL", "")
    os.environ["OLLAMA_MODEL"] = model_name
    try:
        evaluator = LexGraphEvaluator(
            use_local_llm=True,
            pipeline_version=pipeline_version,
            use_wandb=False,
            ragas_timeout_sec=ragas_timeout_sec,
            ragas_max_workers=ragas_max_workers,
        )
        dataset = evaluator._generate_answers(cases, use_rag=use_rag)
        scores_raw = evaluator._evaluate(dataset)
        scores_raw["pipeline_version"] = pipeline_version
        scores_raw["test_count"] = len(dataset)
        scores_raw["use_rag"] = use_rag
        return scores_raw, dataset
    finally:
        os.environ["OLLAMA_MODEL"] = prev_model


def _build_cases_table(wandb_module, scores: dict, dataset: list[dict], label: str, use_rag: bool):
    raw = scores.get("raw", [])
    if not raw:
        return None
    table = wandb_module.Table(columns=[
        "question", "answer", "faithfulness", "answer_relevancy",
        "context_precision", "context_recall", "jurisdiction", "pass", "model", "use_rag",
    ])
    for row, case in zip(raw, dataset):
        faith = row.get("faithfulness", 0)
        table.add_data(
            case["question"],
            case["answer"][:300],
            faith,
            row.get("answer_relevancy", 0),
            row.get("context_precision", 0),
            row.get("context_recall", 0),
            case.get("jurisdiction", ""),
            faith >= FAITHFULNESS_TARGET,
            label,
            use_rag,
        )
    return table


def compare_four_way(
    base_model: str,
    finetuned_model: str,
    version: str,
    eval_dataset: str | None,
    max_examples: int,
    sample_seed: int,
    ragas_timeout_sec: int,
    ragas_max_workers: int,
) -> None:
    try:
        import wandb
    except ImportError:
        raise SystemExit("wandb not installed. Run: pip install wandb")

    cases = _load_cases(eval_dataset, max_examples=max_examples, seed=sample_seed)
    if cases is not None:
        print(f"[4way] loaded {len(cases)} eval cases (max_examples={max_examples})")

    run = wandb.init(
        project="lexgraph-finetune",
        job_type="eval-4way",
        name=f"4way-{version}-{int(time.time())}",
        config={
            "base_model": base_model,
            "finetuned_model": finetuned_model,
            "version": version,
            "eval_dataset": eval_dataset or "evaluation.test_cases.TEST_CASES",
            "faithfulness_target": FAITHFULNESS_TARGET,
            "answer_relevancy_target": ANSWER_RELEVANCY_TARGET,
            "conditions": ["A_base_no_rag", "B_base_rag", "C_ft_no_rag", "D_ft_rag"],
            "max_examples": max_examples,
            "sample_seed": sample_seed,
            "ragas_timeout_sec": ragas_timeout_sec,
            "ragas_max_workers": ragas_max_workers,
        },
    )

    experiments = [
        ("A_base_no_rag", base_model, False),
        ("B_base_rag", base_model, True),
        ("C_ft_no_rag", finetuned_model, False),
        ("D_ft_rag", finetuned_model, True),
    ]

    results: dict[str, dict] = {}
    for key, model_name, use_rag in experiments:
        print(f"\n[4way] Evaluating {key}: model={model_name}, use_rag={use_rag}")
        scores, dataset = _eval_model(
            model_name,
            f"{version}-{key}",
            use_rag=use_rag,
            cases=cases,
            ragas_timeout_sec=ragas_timeout_sec,
            ragas_max_workers=ragas_max_workers,
        )
        results[key] = scores

        wandb.log({f"{key}/{m}": scores.get(m, 0) for m in METRICS})
        table = _build_cases_table(wandb, scores, dataset, model_name, use_rag)
        if table:
            wandb.log({f"4way/{key}_cases": table})

    # Effect decomposition
    deltas = {
        "ft_effect_no_rag": {
            m: round(results["C_ft_no_rag"].get(m, 0) - results["A_base_no_rag"].get(m, 0), 4)
            for m in METRICS
        },
        "rag_effect_base": {
            m: round(results["B_base_rag"].get(m, 0) - results["A_base_no_rag"].get(m, 0), 4)
            for m in METRICS
        },
        "rag_effect_finetuned": {
            m: round(results["D_ft_rag"].get(m, 0) - results["C_ft_no_rag"].get(m, 0), 4)
            for m in METRICS
        },
        "ft_effect_with_rag": {
            m: round(results["D_ft_rag"].get(m, 0) - results["B_base_rag"].get(m, 0), 4)
            for m in METRICS
        },
    }

    for effect_name, metrics in deltas.items():
        wandb.log({f"delta/{effect_name}/{m}": v for m, v in metrics.items()})

    summary = wandb.Table(columns=["comparison", "metric", "delta"])
    for effect_name, metrics in deltas.items():
        for m, v in metrics.items():
            summary.add_data(effect_name, m, v)
    wandb.log({"4way/effect_summary": summary})

    wandb.summary["D_ft_rag_passes_target"] = (
        results["D_ft_rag"].get("faithfulness", 0) >= FAITHFULNESS_TARGET
        and results["D_ft_rag"].get("answer_relevancy", 0) >= ANSWER_RELEVANCY_TARGET
    )
    wandb.finish()

    print("\n" + "─" * 72)
    print("  4-way Evaluation Summary (Base/FT × RAG off/on)")
    print("─" * 72)
    print(f"  {'Condition':<18} {'Faith':>8} {'AnsRel':>8} {'CtxPrec':>8} {'CtxRec':>8}")
    print("─" * 72)
    for key in ["A_base_no_rag", "B_base_rag", "C_ft_no_rag", "D_ft_rag"]:
        s = results[key]
        print(
            f"  {key:<18} {s.get('faithfulness',0):>8.4f} {s.get('answer_relevancy',0):>8.4f} "
            f"{s.get('context_precision',0):>8.4f} {s.get('context_recall',0):>8.4f}"
        )
    print("─" * 72)

    print("\n[effect deltas]")
    for effect_name, metrics in deltas.items():
        print(f"  {effect_name}:")
        for m, v in metrics.items():
            sign = "+" if v >= 0 else ""
            print(f"    - {m:<18}: {sign}{v:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="4-way comparison: base/ft with and without RAG"
    )
    parser.add_argument("--base_model", default="qwen2.5:1.5b")
    parser.add_argument("--finetuned_model", default="lexgraph-legal")
    parser.add_argument("--version", default="v2")
    parser.add_argument(
        "--eval_dataset",
        default=None,
        help="Optional JSON eval dataset path. If omitted, uses evaluation.test_cases.TEST_CASES",
    )
    parser.add_argument(
        "--max_examples",
        type=int,
        default=12,
        help="Number of evaluation rows to run. Keep small first to avoid timeout storms.",
    )
    parser.add_argument("--sample_seed", type=int, default=42)
    parser.add_argument("--ragas_timeout_sec", type=int, default=120)
    parser.add_argument("--ragas_max_workers", type=int, default=1)
    args = parser.parse_args()
    compare_four_way(
        args.base_model,
        args.finetuned_model,
        args.version,
        args.eval_dataset,
        args.max_examples,
        args.sample_seed,
        args.ragas_timeout_sec,
        args.ragas_max_workers,
    )
