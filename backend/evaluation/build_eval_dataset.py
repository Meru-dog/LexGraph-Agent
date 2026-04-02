"""Build evaluation datasets for 4-condition (Base/FT × RAG on/off) experiments.

This script supports two sources:
1) Local custom test cases (backend/evaluation/test_cases.py)
2) Optional Hugging Face datasets (if available)

Output format (JSON list):
[
  {
    "question": "...",
    "ground_truth": "...",
    "jurisdiction": "JP|US",
    "contexts": ["optional gold contexts ..."]
  }
]
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from evaluation.test_cases import TEST_CASES


def _normalize(item: dict) -> dict | None:
    q = item.get("question") or item.get("input") or item.get("prompt")
    a = item.get("ground_truth") or item.get("reference") or item.get("answer") or item.get("output")
    if not q or not a:
        return None
    contexts = item.get("contexts") or item.get("gold_contexts") or []
    return {
        "question": str(q).strip(),
        "ground_truth": str(a).strip(),
        "jurisdiction": item.get("jurisdiction", "JP"),
        "contexts": [str(c).strip() for c in contexts if str(c).strip()],
    }


def _load_hf_examples(max_examples: int) -> list[dict]:
    """Try loading legal QA examples from HF, then normalize to evaluator format."""
    from datasets import load_dataset

    candidates = [
        # JP / bilingual legal QA
        ("legalscape/jlawtext", "train", "JP"),
        # US legal QA/contract tasks fallback
        ("theatticusproject/cuad", "train", "US"),
    ]

    out: list[dict] = []
    for dataset_name, split, jurisdiction in candidates:
        try:
            ds = load_dataset(dataset_name, split=split)
        except Exception as e:
            print(f"[build_eval_dataset] skip {dataset_name}: {e}")
            continue

        for ex in ds:
            row = _normalize({
                "question": ex.get("question") or ex.get("input") or ex.get("text"),
                "ground_truth": ex.get("answer") or ex.get("output") or ex.get("label"),
                "jurisdiction": jurisdiction,
                "contexts": [ex.get("context", "")] if ex.get("context") else [],
            })
            if not row:
                continue
            out.append(row)
            if len(out) >= max_examples:
                return out

    return out


def build_dataset(max_examples: int, include_hf: bool, seed: int) -> list[dict]:
    random.seed(seed)

    custom = [_normalize(x) for x in TEST_CASES]
    custom = [x for x in custom if x]

    dataset = custom
    if include_hf:
        hf_rows = _load_hf_examples(max_examples=max_examples)
        dataset.extend(hf_rows)

    random.shuffle(dataset)
    return dataset[:max_examples]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build legal eval dataset for 4-condition experiments")
    parser.add_argument("--max_examples", type=int, default=120)
    parser.add_argument("--include_hf", action="store_true", help="include Hugging Face datasets if available")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        default="backend/eval_data/legal_eval_4way.json",
        help="output JSON path",
    )
    args = parser.parse_args()

    rows = build_dataset(args.max_examples, args.include_hf, args.seed)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[build_eval_dataset] wrote {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
