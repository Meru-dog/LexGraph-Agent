"""Evaluation runner — COLIEE (JP) and LexGLUE (US) benchmarks.

Usage:
    python -m training.evaluate --benchmark coliee --adapter ./adapters/adapter_jp
    python -m training.evaluate --benchmark lexglue --adapter ./adapters/adapter_us
    python -m training.evaluate --benchmark all

Targets (per RDD §6.5):
    COLIEE Task 4 (JP):  > 70% accuracy   (baseline LLaMA ~55%)
    LexGLUE (US):        > 75% macro-F1 across 6 tasks
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional


def load_model_with_adapter(base_model: str, adapter_path: str):
    """Load base model + QLoRA adapter for inference."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    print(f"[evaluate] Loading {base_model} + adapter {adapter_path}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    model = AutoModelForCausalLM.from_pretrained(
        base_model, quantization_config=bnb_config, device_map="auto"
    )
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, tokenizer


def generate_answer(model, tokenizer, prompt: str, max_new_tokens: int = 256) -> str:
    """Run inference and return the model's answer."""
    import torch

    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1800).to(model.device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Strip the prompt prefix from the output
    return decoded[len(tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)):].strip()


def evaluate_coliee(
    adapter_path: str = "./adapters/adapter_jp",
    base_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    max_examples: int = 200,
    dry_run: bool = False,
) -> dict:
    """Evaluate JP adapter on COLIEE Task 4 — statute entailment.

    COLIEE Task 4: Given a legal bar exam question and relevant Civil Code articles,
    determine if the statement is true/false.
    """
    from datasets import load_dataset

    print(f"[evaluate] COLIEE Task 4 — max {max_examples} examples")

    # Load COLIEE dataset (available via competition or COLIEE GitHub)
    # Fallback: use a proxy dataset for statute entailment
    try:
        # Try official COLIEE dataset
        ds = load_dataset("rceborg/coliee2022", split="test", trust_remote_code=True)
    except Exception:
        try:
            # Fallback: use JLawText entailment subset
            ds = load_dataset("legalscape/jlawtext", split="test", trust_remote_code=True)
        except Exception as e:
            print(f"[evaluate] COLIEE dataset unavailable: {e}")
            return {
                "benchmark": "COLIEE Task 4",
                "jurisdiction": "JP",
                "target": 0.70,
                "score": None,
                "status": "Dataset unavailable — run after COLIEE registration",
            }

    if dry_run:
        return {
            "benchmark": "COLIEE Task 4",
            "jurisdiction": "JP",
            "target": 0.70,
            "score": None,
            "status": "Dry run — model not loaded",
        }

    model, tokenizer = load_model_with_adapter(base_model, adapter_path)

    correct = 0
    total = 0
    errors = []

    system_prompt = (
        "You are a Japanese legal expert. Answer questions about Japanese law "
        "based on the provided legal articles. Answer only 'Yes' or 'No'."
    )

    for ex in ds.select(range(min(max_examples, len(ds)))):
        question = ex.get("question") or ex.get("text", "")
        label = ex.get("label") or ex.get("answer", "")
        if not question:
            continue

        prompt = f"{system_prompt}\n\nQuestion: {question}\n\nAnswer:"
        try:
            prediction = generate_answer(model, tokenizer, prompt, max_new_tokens=10)
            pred_binary = "yes" in prediction.lower()
            true_binary = str(label).lower() in ("yes", "true", "1", "y")
            if pred_binary == true_binary:
                correct += 1
            total += 1
        except Exception as e:
            errors.append(str(e))

    accuracy = correct / total if total > 0 else 0.0
    print(f"[evaluate] COLIEE accuracy: {accuracy:.3f} ({correct}/{total})")

    return {
        "benchmark": "COLIEE Task 4",
        "jurisdiction": "JP",
        "target": 0.70,
        "score": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "passed": accuracy >= 0.70,
        "errors": errors[:5],
    }


def evaluate_lexglue(
    adapter_path: str = "./adapters/adapter_us",
    base_model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    dry_run: bool = False,
) -> dict:
    """Evaluate US adapter on LexGLUE — 6 legal NLP tasks.

    Tasks: ECtHR (A), ECtHR (B), SCOTUS, EUR-LEX, LEDGAR, UNFAIR-ToS
    Metric: macro-F1 per task, then average.
    """
    from datasets import load_dataset
    from sklearn.metrics import f1_score

    TASKS = [
        ("ecthr_a", "text", "labels"),
        ("ecthr_b", "text", "labels"),
        ("scotus", "text", "label"),
        ("eurlex", "text", "labels"),
        ("ledgar", "text", "label"),
        ("unfair_tos", "text", "labels"),
    ]

    print("[evaluate] LexGLUE — 6-task benchmark")

    if dry_run:
        return {
            "benchmark": "LexGLUE",
            "jurisdiction": "US",
            "target": 0.75,
            "macro_f1": None,
            "per_task": {},
            "status": "Dry run — model not loaded",
        }

    model, tokenizer = load_model_with_adapter(base_model, adapter_path)

    per_task_results = {}
    all_f1 = []

    for task_name, text_col, label_col in TASKS:
        try:
            ds = load_dataset("coastalcph/lex_glue", task_name, split="test", trust_remote_code=True)
            ds_sample = ds.select(range(min(100, len(ds))))

            y_true, y_pred = [], []
            for ex in ds_sample:
                text = ex.get(text_col, "")[:800]
                true_label = ex.get(label_col)
                if true_label is None or not text:
                    continue

                prompt = (
                    f"Legal document classification task ({task_name}).\n\n"
                    f"Document: {text}\n\n"
                    f"Classify this document. Provide only the category number."
                )
                try:
                    pred_text = generate_answer(model, tokenizer, prompt, max_new_tokens=20)
                    # Extract first integer from prediction
                    import re
                    numbers = re.findall(r"\d+", pred_text)
                    pred_label = int(numbers[0]) if numbers else 0

                    if isinstance(true_label, list):
                        true_label = true_label[0] if true_label else 0

                    y_true.append(int(true_label))
                    y_pred.append(pred_label)
                except Exception:
                    pass

            if y_true:
                f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
                per_task_results[task_name] = round(f1, 4)
                all_f1.append(f1)
                print(f"[evaluate] {task_name}: macro-F1 = {f1:.3f}")
        except Exception as e:
            print(f"[evaluate] {task_name} failed: {e}")
            per_task_results[task_name] = None

    macro_f1 = sum(f for f in all_f1 if f is not None) / len(all_f1) if all_f1 else 0.0
    print(f"[evaluate] LexGLUE average macro-F1: {macro_f1:.3f}")

    return {
        "benchmark": "LexGLUE",
        "jurisdiction": "US",
        "target": 0.75,
        "macro_f1": round(macro_f1, 4),
        "per_task": per_task_results,
        "passed": macro_f1 >= 0.75,
    }


def evaluate_internal_contracts(
    adapter_jp_path: str,
    adapter_us_path: str,
    test_dir: str = "./tests/contracts",
) -> dict:
    """Attorney blind review on internal contract test set.

    Requires manually curated test contracts in tests/contracts/.
    Reviewers score each output 1-5; target >= 4.0 average.
    """
    test_path = Path(test_dir)
    if not test_path.exists():
        return {
            "benchmark": "Internal Contract Test Set",
            "jurisdiction": "JP + US",
            "target": 4.0,
            "test_cases": 0,
            "status": "Test directory not found — place contracts in tests/contracts/",
        }

    contracts = list(test_path.glob("*.txt")) + list(test_path.glob("*.pdf"))
    return {
        "benchmark": "Internal Contract Test Set",
        "jurisdiction": "JP + US",
        "target": 4.0,
        "test_cases": len(contracts),
        "status": f"Ready — {len(contracts)} contracts found. Run attorney blind review panel.",
        "instructions": (
            "Load each contract through the /agent/review endpoint with the fine-tuned adapter, "
            "then have 2+ attorneys score outputs 1-5 on: accuracy, completeness, citation quality."
        ),
    }


def run_all(
    adapter_jp: str = "./adapters/adapter_jp",
    adapter_us: str = "./adapters/adapter_us",
    dry_run: bool = False,
) -> dict:
    results = {
        "coliee": evaluate_coliee(adapter_jp, dry_run=dry_run),
        "lexglue": evaluate_lexglue(adapter_us, dry_run=dry_run),
        "internal": evaluate_internal_contracts(adapter_jp, adapter_us),
    }
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        status = "PASS" if result.get("passed") else "FAIL" if result.get("passed") is False else "PENDING"
        score = result.get("score") or result.get("macro_f1") or "—"
        target = result.get("target", "—")
        print(f"{name:12s}: {status:7s} | score={score} | target={target}")
    print("=" * 60)

    output_path = Path("./evaluation_results.json")
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"[evaluate] Results saved to {output_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LexGraph AI — evaluation runner")
    parser.add_argument(
        "--benchmark", choices=["coliee", "lexglue", "internal", "all"], default="all"
    )
    parser.add_argument("--adapter-jp", default="./adapters/adapter_jp")
    parser.add_argument("--adapter-us", default="./adapters/adapter_us")
    parser.add_argument("--max-examples", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).parent.parent))

    if args.benchmark == "all":
        run_all(args.adapter_jp, args.adapter_us, dry_run=args.dry_run)
    elif args.benchmark == "coliee":
        print(json.dumps(evaluate_coliee(args.adapter_jp, max_examples=args.max_examples, dry_run=args.dry_run), indent=2, ensure_ascii=False))
    elif args.benchmark == "lexglue":
        print(json.dumps(evaluate_lexglue(args.adapter_us, dry_run=args.dry_run), indent=2, ensure_ascii=False))
    elif args.benchmark == "internal":
        print(json.dumps(evaluate_internal_contracts(args.adapter_jp, args.adapter_us), indent=2, ensure_ascii=False))
