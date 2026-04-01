"""Compare base model vs fine-tuned model using RAGAS metrics, logged to W&B.

Loads two Ollama models (base and fine-tuned), runs RAGAS evaluation on both,
and logs a side-by-side comparison to a single W&B run in project 'lexgraph-finetune'.

Usage:
    python fine_tune/evaluate_finetune.py \
        --base_model qwen2.5:1.5b \
        --finetuned_model lexgraph-legal \
        --version v1.0

Requirements:
    - Ollama running with both models loaded
    - pip install ragas wandb datasets
    - Neo4j + Supabase configured for hybrid_search
"""

import argparse
import os
import sys
import time

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Metric keys ───────────────────────────────────────────────────────────────
METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
FAITHFULNESS_TARGET = 0.75
ANSWER_RELEVANCY_TARGET = 0.70


def _eval_model(model_name: str, pipeline_version: str) -> tuple[dict, list[dict]]:
    """Run RAGAS evaluation for a given Ollama model name.

    Returns (scores dict, dataset list).
    """
    from evaluation.ragas_evaluator import LexGraphEvaluator

    prev_model = os.environ.get("OLLAMA_MODEL", "")
    os.environ["OLLAMA_MODEL"] = model_name
    try:
        evaluator = LexGraphEvaluator(
            use_local_llm=True,
            pipeline_version=pipeline_version,
            use_wandb=False,   # We log manually in a single comparative run
        )
        dataset = evaluator._generate_answers(None)
        scores_raw = evaluator._evaluate(dataset)
        scores_raw["pipeline_version"] = pipeline_version
        scores_raw["test_count"] = len(dataset)
        return scores_raw, dataset
    finally:
        os.environ["OLLAMA_MODEL"] = prev_model


def _build_cases_table(wandb_module, scores: dict, dataset: list[dict], label: str):
    """Build a W&B Table with per-case metrics for one model."""
    raw = scores.get("raw", [])
    if not raw:
        return None
    table = wandb_module.Table(columns=[
        "question", "answer", "faithfulness", "answer_relevancy",
        "context_precision", "context_recall", "jurisdiction", "pass", "model",
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
        )
    return table


def compare(base_model: str, finetuned_model: str, version: str) -> None:
    try:
        import wandb
    except ImportError:
        raise SystemExit("wandb not installed. Run: pip install wandb")

    run = wandb.init(
        project="lexgraph-finetune",
        job_type="eval-compare",
        name=f"compare-{version}-{int(time.time())}",
        config={
            "base_model":       base_model,
            "finetuned_model":  finetuned_model,
            "version":          version,
            "faithfulness_target":     FAITHFULNESS_TARGET,
            "answer_relevancy_target": ANSWER_RELEVANCY_TARGET,
        },
    )

    # ── Evaluate base model ───────────────────────────────────────────────────
    print(f"\n[compare] Evaluating base model: {base_model}")
    base_scores, base_dataset = _eval_model(base_model, f"{version}-base")

    wandb.log({f"base/{m}": base_scores.get(m, 0) for m in METRICS})
    base_table = _build_cases_table(wandb, base_scores, base_dataset, base_model)
    if base_table:
        wandb.log({"compare/base_cases": base_table})

    # ── Evaluate fine-tuned model ─────────────────────────────────────────────
    print(f"\n[compare] Evaluating fine-tuned model: {finetuned_model}")
    ft_scores, ft_dataset = _eval_model(finetuned_model, f"{version}-finetuned")

    wandb.log({f"finetuned/{m}": ft_scores.get(m, 0) for m in METRICS})
    ft_table = _build_cases_table(wandb, ft_scores, ft_dataset, finetuned_model)
    if ft_table:
        wandb.log({"compare/finetuned_cases": ft_table})

    # ── Delta metrics ─────────────────────────────────────────────────────────
    deltas = {m: round(ft_scores.get(m, 0) - base_scores.get(m, 0), 4) for m in METRICS}
    wandb.log({f"delta/{m}": v for m, v in deltas.items()})

    # ── Summary ───────────────────────────────────────────────────────────────
    wandb.summary["faithfulness_delta"]      = deltas["faithfulness"]
    wandb.summary["answer_relevancy_delta"]  = deltas["answer_relevancy"]
    wandb.summary["faithfulness_improved"]   = deltas["faithfulness"] > 0
    wandb.summary["finetuned_passes_target"] = (
        ft_scores.get("faithfulness", 0) >= FAITHFULNESS_TARGET
        and ft_scores.get("answer_relevancy", 0) >= ANSWER_RELEVANCY_TARGET
    )

    # ── Combined comparison table ─────────────────────────────────────────────
    cmp_table = wandb.Table(
        columns=["metric", "base", "finetuned", "delta", "target", "finetuned_passes"]
    )
    targets = {"faithfulness": FAITHFULNESS_TARGET, "answer_relevancy": ANSWER_RELEVANCY_TARGET}
    for m in METRICS:
        b = base_scores.get(m, 0)
        f = ft_scores.get(m, 0)
        t = targets.get(m)
        cmp_table.add_data(
            m, round(b, 4), round(f, 4), round(f - b, 4),
            t if t else "—",
            (f >= t) if t else "—",
        )
    wandb.log({"compare/summary": cmp_table})

    wandb.finish()

    # ── Console output ────────────────────────────────────────────────────────
    print("\n" + "─" * 60)
    print(f"  Fine-Tuning Evaluation: {base_model} → {finetuned_model}")
    print("─" * 60)
    print(f"  {'Metric':<22} {'Base':>8}  {'Fine-tuned':>10}  {'Delta':>8}")
    print("─" * 60)
    for m in METRICS:
        b = base_scores.get(m, 0)
        f = ft_scores.get(m, 0)
        d = f - b
        sign = "+" if d >= 0 else ""
        print(f"  {m:<22} {b:>8.4f}  {f:>10.4f}  {sign}{d:>7.4f}")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare base vs fine-tuned model with RAGAS + W&B"
    )
    parser.add_argument("--base_model",      default="qwen2.5:1.5b",
                        help="Ollama model name for the base (untuned) model")
    parser.add_argument("--finetuned_model", default="lexgraph-legal",
                        help="Ollama model name for the fine-tuned model")
    parser.add_argument("--version",         default="v1",
                        help="Version tag for W&B run naming")
    args = parser.parse_args()
    compare(args.base_model, args.finetuned_model, args.version)
