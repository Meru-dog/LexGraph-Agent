"""LoRA fine-tuning script for LexGraph Legal model.

Fine-tunes Llama 3.1 8B on JP/US legal domain data using QLoRA (4-bit + LoRA).
Produces adapter weights that can be merged and served via Ollama.

Requirements (in addition to requirements.txt):
    pip install transformers peft bitsandbytes datasets accelerate trl

Usage:
    python fine_tune/train_lora.py \
        --base_model NousResearch/Meta-Llama-3.1-8B-Instruct \
        --data_path fine_tune/data/legal_qa.jsonl \
        --output_dir fine_tune/adapters/lexgraph-legal \
        --epochs 3

Data format (JSONL, one example per line):
    {"instruction": "Analyze the following JP contract clause...", "output": "..."}
"""

import argparse
import json
import os


def load_dataset_from_jsonl(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def format_prompt(example: dict) -> str:
    """Llama 3.1 instruction format."""
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n"
        "You are LexGraph Legal, an expert AI assistant specializing in JP/US corporate law, "
        "M&A due diligence, and contract review. Respond in the same language as the user.<|eot_id|>\n"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{example['instruction']}<|eot_id|>\n"
        "<|start_header_id|>assistant<|end_header_id|>\n"
        f"{example['output']}<|eot_id|>"
    )


def _detect_device():
    """Detect best available device: MPS (Apple Silicon) > CUDA > CPU."""
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _run_ragas_eval(label: str, wandb_run) -> dict:
    """Run RAGAS evaluation and log results under a given label prefix."""
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from evaluation.ragas_evaluator import LexGraphEvaluator
        evaluator = LexGraphEvaluator(use_wandb=False)  # we log manually below
        scores = evaluator.run()
        if wandb_run:
            import wandb
            wandb.log({
                f"{label}/faithfulness":      scores.get("faithfulness", 0),
                f"{label}/answer_relevancy":  scores.get("answer_relevancy", 0),
                f"{label}/context_precision": scores.get("context_precision", 0),
                f"{label}/context_recall":    scores.get("context_recall", 0),
            })
        print(f"[eval/{label}] faithfulness={scores.get('faithfulness'):.4f}")
        return scores
    except Exception as e:
        print(f"[eval/{label}] skipped: {e}")
        return {}


def train(
    base_model: str = "NousResearch/Meta-Llama-3.1-8B-Instruct",
    data_path: str = "fine_tune/data/legal_qa.jsonl",
    output_dir: str = "fine_tune/adapters/lexgraph-legal",
    epochs: int = 3,
    batch_size: int = 1,
    learning_rate: float = 2e-4,
    max_seq_length: int = 512,
    adapter: str = "JP",          # "JP" | "US" — for W&B run naming
    lora_rank: int = 16,
    lora_alpha: int = 32,
    eval_ragas: bool = False,     # Run RAGAS before & after to measure improvement
    local_files_only: bool = False,  # True = cache only (no hf.co download); use for airgap
):
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import LoraConfig, get_peft_model, TaskType
        from trl import SFTTrainer, SFTConfig
        from datasets import Dataset
    except ImportError as e:
        raise SystemExit(
            f"Missing fine-tuning deps: {e}\n"
            "Run: pip install transformers peft bitsandbytes datasets accelerate trl"
        )

    device = _detect_device()
    print(f"Device: {device}")

    # ── W&B initialisation (RDD §12.5 / §13) ─────────────────────────────────
    _wandb_run = None
    try:
        import wandb, time, torch as _torch
        sys_info: dict = {"torch_version": _torch.__version__, "device": device}
        if device == "cuda":
            sys_info["gpu_name"] = _torch.cuda.get_device_name(0)
            sys_info["gpu_memory_gb"] = round(
                _torch.cuda.get_device_properties(0).total_memory / 1e9, 2
            )
        _wandb_run = wandb.init(
            project="lexgraph-finetune",
            name=f"{base_model.split('/')[-1]}-{adapter.lower()}-r{lora_rank}-{int(time.time())}",
            config={
                "base_model":     base_model,
                "adapter":        adapter,
                "lora_rank":      lora_rank,
                "lora_alpha":     lora_alpha,
                "epochs":         epochs,
                "batch_size":     batch_size,
                "lr":             learning_rate,
                "max_seq_length": max_seq_length,
                "data_path":      data_path,
                **sys_info,
            },
        )
        print(f"[wandb] Run: {_wandb_run.url}")
    except Exception as e:
        print(f"[wandb] init skipped (non-fatal): {e}")

    print(f"Loading dataset from {data_path}...")
    raw = load_dataset_from_jsonl(data_path)
    texts = [format_prompt(ex) for ex in raw]
    dataset = Dataset.from_dict({"text": texts})

    # ── Log dataset statistics ────────────────────────────────────────────────
    if _wandb_run:
        try:
            import wandb
            token_lengths = [len(t.split()) for t in texts]
            wandb.config.update({
                "dataset_size": len(texts),
                "avg_tokens":   round(sum(token_lengths) / len(token_lengths), 1),
                "max_tokens":   max(token_lengths),
            }, allow_val_change=True)
        except Exception:
            pass

    print(f"Loading base model: {base_model}")
    # Mac MPS/CPU: load in float16 (bitsandbytes 4-bit not supported on Apple Silicon)
    dtype = torch.float16
    tokenizer = AutoTokenizer.from_pretrained(
        base_model, trust_remote_code=True, local_files_only=local_files_only
    )
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        dtype=dtype,
        device_map={"": device},
        trust_remote_code=True,
        local_files_only=local_files_only,
    )
    model.config.use_cache = False
    model.enable_input_require_grads()

    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = SFTConfig(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=8,
        gradient_checkpointing=True,
        warmup_steps=5,
        learning_rate=learning_rate,
        fp16=False,
        bf16=False,
        logging_steps=1,
        save_strategy="epoch",
        optim="adamw_torch",
        report_to="wandb" if _wandb_run else "none",
        max_length=max_seq_length,
        dataset_text_field="text",
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
    )

    # ── Pre-training RAGAS baseline ───────────────────────────────────────────
    baseline_scores: dict = {}
    if eval_ragas:
        print("[eval] Running pre-training RAGAS baseline...")
        baseline_scores = _run_ragas_eval("eval/before", _wandb_run)

    print("Starting training...")
    train_result = trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"\nAdapter saved to {output_dir}")

    # ── Log training summary ──────────────────────────────────────────────────
    if _wandb_run:
        try:
            import wandb
            wandb.summary["train_loss"]        = train_result.training_loss
            wandb.summary["train_runtime_sec"] = round(train_result.metrics.get("train_runtime", 0), 1)
            wandb.summary["samples_per_sec"]   = round(train_result.metrics.get("train_samples_per_second", 0), 2)
            # Capture full step-level log history (covers loss, lr, grad_norm)
            for entry in trainer.state.log_history:
                step = entry.get("step")
                if step is not None:
                    wandb.log(
                        {f"train/{k}": v for k, v in entry.items() if k not in ("step", "epoch")},
                        step=step,
                    )
        except Exception as e:
            print(f"[wandb] training summary error (non-fatal): {e}")

    # ── Post-training RAGAS evaluation ───────────────────────────────────────
    if eval_ragas:
        print("[eval] Running post-training RAGAS evaluation...")
        after_scores = _run_ragas_eval("eval/after", _wandb_run)
        if _wandb_run and baseline_scores and after_scores:
            try:
                import wandb
                delta = after_scores.get("faithfulness", 0) - baseline_scores.get("faithfulness", 0)
                wandb.summary["faithfulness_delta"] = round(delta, 4)
                wandb.summary["faithfulness_improved"] = delta > 0
            except Exception:
                pass

    # ── W&B: save adapter as Artifact ────────────────────────────────────────
    if _wandb_run:
        try:
            import wandb
            artifact = wandb.Artifact(
                name=f"lexgraph-adapter-{adapter.lower()}",
                type="model",
                description=f"QLoRA adapter {adapter} — {base_model}",
                metadata={
                    "base_model":  base_model,
                    "adapter":     adapter,
                    "lora_rank":   lora_rank,
                    "lora_alpha":  lora_alpha,
                    "epochs":      epochs,
                    "data_path":   data_path,
                },
            )
            artifact.add_dir(output_dir)
            _wandb_run.log_artifact(artifact)
            _wandb_run.finish()
            print(f"[wandb] Adapter artifact logged")
        except Exception as e:
            print(f"[wandb] artifact log error (non-fatal): {e}")

    print("\nNext step: merge & export to GGUF for Ollama:")
    print(f"  python fine_tune/export_gguf.py --adapter {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Llama 3.1 8B for LexGraph Legal")
    # Qwen2.5-1.5B: ~3GB, multilingual JP/EN, fits on Mac MPS, not gated
    # Alternative (needs more RAM): NousResearch/Meta-Llama-3.1-8B-Instruct
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--data_path", default="fine_tune/data/legal_qa.jsonl")
    parser.add_argument("--output_dir", default="fine_tune/adapters/lexgraph-legal")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--adapter", default="JP", choices=["JP", "US"])
    parser.add_argument("--lora_rank", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument(
        "--eval_ragas", action="store_true",
        help="Run RAGAS evaluation before and after training to measure improvement"
    )
    parser.add_argument(
        "--local_files_only", action="store_true",
        help="Use only HF cache (no network). Default: download from huggingface.co if missing.",
    )
    args = parser.parse_args()
    train(
        base_model=args.base_model,
        data_path=args.data_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        adapter=args.adapter,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_ragas=args.eval_ragas,
        local_files_only=args.local_files_only,
    )
