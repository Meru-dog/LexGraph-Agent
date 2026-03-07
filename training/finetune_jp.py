"""QLoRA fine-tuning — JP legal adapter for LLaMA 3.1 8B (or Swallow-8B).

Usage:
    python -m training.finetune_jp
    python -m training.finetune_jp --swallow         # Use Swallow-8B base model
    python -m training.finetune_jp --dry-run
    python -m training.finetune_jp --max-examples 100

Hardware requirements:
    Single A100 40GB or 2x A10G. Est. 4-6 hours for full 1,800-example run.

Output: ./adapters/adapter_jp/
"""

import argparse
import os
import sys
from pathlib import Path

# Per RDD design decision #1: use Swallow-8B for JP-heavy deployments
BASE_MODEL_LLAMA = os.getenv("BASE_MODEL_JP", "meta-llama/Meta-Llama-3.1-8B-Instruct")
BASE_MODEL_SWALLOW = "tokyotech-llm/Swallow-8B-instruct-v0.1"
OUTPUT_DIR = Path(os.getenv("ADAPTER_JP_PATH", "./adapters/adapter_jp"))

LORA_CONFIG = dict(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)

TRAINING_ARGS = dict(
    output_dir=str(OUTPUT_DIR),
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_ratio=0.05,
    lr_scheduler_type="cosine",
    bf16=True,
    logging_steps=25,
    save_steps=200,
    save_total_limit=3,
    max_seq_length=2048,
    dataset_text_field="text",
    report_to="tensorboard",
    logging_dir=str(OUTPUT_DIR / "logs"),
    load_best_model_at_end=False,
)


def train(use_swallow: bool = False, dry_run: bool = False, max_examples: int | None = None) -> None:
    from datasets import Dataset

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from training.datasets.jp_loader import load_all_jp_datasets
    from training.datasets.format_instructions import convert_dataset_to_instructions

    base_model = BASE_MODEL_SWALLOW if use_swallow else BASE_MODEL_LLAMA
    print(f"[finetune_jp] Base model: {base_model}")

    print("[finetune_jp] Loading datasets...")
    raw_data = load_all_jp_datasets()
    if max_examples:
        raw_data = raw_data[:max_examples]
    print(f"[finetune_jp] {len(raw_data)} training examples loaded")

    texts = convert_dataset_to_instructions(raw_data, jurisdiction="JP", template="llama3_chat")
    dataset = Dataset.from_dict({"text": texts})
    print(f"[finetune_jp] Dataset formatted: {len(dataset)} examples")

    if dry_run:
        print("[finetune_jp] Dry run complete — skipping model load and training")
        print(f"[finetune_jp] Sample:\n{texts[0][:500]}...")
        return

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[finetune_jp] Loading base model: {base_model}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    # Swallow-8B may use a different tokenizer config
    tokenizer_kwargs = {"trust_remote_code": True} if use_swallow else {}
    tokenizer = AutoTokenizer.from_pretrained(base_model, **tokenizer_kwargs)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=use_swallow,
    )
    model = prepare_model_for_kbit_training(model)

    lora_cfg = LoraConfig(**LORA_CONFIG)
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    sft_config = SFTConfig(**TRAINING_ARGS)
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=sft_config,
    )

    print("[finetune_jp] Starting training...")
    trainer.train()

    print(f"[finetune_jp] Saving adapter to {OUTPUT_DIR}")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))

    # Save metadata for adapter_router
    import json
    meta = {"base_model": base_model, "jurisdiction": "JP", "use_swallow": use_swallow}
    (OUTPUT_DIR / "adapter_meta.json").write_text(json.dumps(meta, indent=2))
    print("[finetune_jp] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QLoRA fine-tuning: JP legal adapter")
    parser.add_argument("--swallow", action="store_true", help="Use Swallow-8B base model")
    parser.add_argument("--dry-run", action="store_true", help="Load data only, skip training")
    parser.add_argument("--max-examples", type=int, default=None, help="Limit examples (smoke test)")
    parser.add_argument("--base-model", type=str, default=None, help="Override base model ID")
    args = parser.parse_args()

    if args.base_model:
        BASE_MODEL_LLAMA = args.base_model

    train(use_swallow=args.swallow, dry_run=args.dry_run, max_examples=args.max_examples)
