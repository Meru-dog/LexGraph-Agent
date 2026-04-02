"""Beginner-friendly RAGAS evaluator runner.

Run from `backend/`:
    python eval_ragas.py

This script keeps evaluation separate from normal backend startup.
It loads eval cases from JSON, generates answers, scores with RAGAS,
and logs aggregate metrics to Weights & Biases.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Callable

import wandb
from datasets import Dataset
from ragas import evaluate


DEFAULT_PROJECT = "lexgraph-rag"
DEFAULT_MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen3")
DEFAULT_DATASET_PATH = Path("eval_data/sample_eval.json")


def _default_generate_answer(question: str, contexts: list[str]) -> str:
    """Fallback answer generator used when no project function is provided."""
    joined = " ".join(contexts)
    if not joined.strip():
        return "参照情報が不足しているため、契約条文を確認して回答してください。"
    return (
        "重大な契約違反があり、催告後も是正されない場合に解除できます。"
    )


def _resolve_generator(import_path: str | None) -> Callable[[str, list[str]], str]:
    """Resolve `module:function` into a callable or return fallback."""
    if not import_path:
        return _default_generate_answer

    if ":" not in import_path:
        raise ValueError(
            "--generator は `module:function` 形式で指定してください。"
        )

    module_name, func_name = import_path.split(":", 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)

    if not callable(func):
        raise TypeError(f"{import_path} は呼び出し可能ではありません。")

    return func


def _validate_item(item: dict, index: int) -> None:
    required = ("question", "contexts", "reference")
    missing = [key for key in required if key not in item]
    if missing:
        raise ValueError(f"行 {index}: 必須キー不足 {missing}")
    if not isinstance(item["contexts"], list) or not all(
        isinstance(text, str) for text in item["contexts"]
    ):
        raise TypeError(
            f"行 {index}: `contexts` は list[str] である必要があります。"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAGAS evaluation from local JSON and log to W&B."
    )
    parser.add_argument(
        "--eval-data",
        default=str(DEFAULT_DATASET_PATH),
        help="評価データJSONのパス (default: eval_data/sample_eval.json)",
    )
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help="W&B project名 (default: lexgraph-rag)",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help="W&Bへ記録するモデル名",
    )
    parser.add_argument(
        "--generator",
        default=None,
        help="回答関数のimport path。例: app.rag:generate_answer",
    )
    args = parser.parse_args()

    eval_path = Path(args.eval_data)
    if not eval_path.exists():
        raise FileNotFoundError(
            f"評価データが見つかりません: {eval_path}\n"
            "先に eval_data/sample_eval.json を作成してください。"
        )

    generate_answer = _resolve_generator(args.generator)

    with eval_path.open("r", encoding="utf-8") as file:
        eval_items = json.load(file)

    if not isinstance(eval_items, list) or not eval_items:
        raise ValueError("評価データは1件以上の配列である必要があります。")

    questions, answers, contexts_list, references = [], [], [], []

    for idx, item in enumerate(eval_items, start=1):
        _validate_item(item, idx)

        question = item["question"]
        contexts = item["contexts"]
        reference = item["reference"]
        answer = generate_answer(question, contexts)

        print("-----")
        print("question:", question)
        print("contexts:", contexts)
        print("answer:", answer)
        print("reference:", reference)

        questions.append(question)
        answers.append(answer)
        contexts_list.append(contexts)
        references.append(reference)

    run = wandb.init(
        project=args.project,
        job_type="eval",
        config={
            "model_name": args.model_name,
            "eval_dataset": str(eval_path),
            "generator": args.generator or "fallback",
        },
    )

    dataset = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
            "ground_truth": references,
        }
    )

    result = evaluate(dataset=dataset)
    print("RAGAS result:", result)

    scores: dict[str, float] = {}
    for key, value in result.items():
        try:
            scores[f"ragas/{key}"] = float(value)
        except Exception:
            print(f"skip key={key}, value={value}")

    print("scores to wandb:", scores)
    run.log(scores)
    run.summary.update(scores)
    run.finish()


if __name__ == "__main__":
    main()
