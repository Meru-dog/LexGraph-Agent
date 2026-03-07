"""QLoRA fine-tuning — US legal adapter for LLaMA 3.1 8B.

Usage:
    python -m training.finetune_us
    python -m training.finetune_us --dry-run          # load data only, no training
    python -m training.finetune_us --max-examples 100 # quick smoke test

Hardware requirements:
    Single A100 40GB or 2x A10G. Est. 4-6 hours for full 1,800-example run.

Output: ./adapters/adapter_us/
"""

import argparse
import os
import sys
from pathlib import Path

BASE_MODEL = os.getenv("BASE_MODEL_US", "meta-llama/Meta-Llama-3.1-8B-Instruct")
OUTPUT_DIR = Path(os.getenv("ADAPTER_US_PATH", "./adapters/adapter_us"))

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
    bf16=True,              # Use bf16 on A100; set fp16=True on A10G
    logging_steps=25,
    save_steps=200,
    save_total_limit=3,
    max_seq_length=2048,
    dataset_text_field="text",
    report_to="tensorboard",
    logging_dir=str(OUTPUT_DIR / "logs"),
    load_best_model_at_end=False,
)


def train(dry_run: bool = False, max_examples: int | None = None) -> None:
    from datasets import Dataset

    sys.path.insert(0, str(Path(__file__).parent.parent))
    from training.datasets.us_loader import load_all_us_datasets
    from training.datasets.format_instructions import convert_dataset_to_instructions

    print("[finetune_us] Loading datasets...")
    raw_data = load_all_us_datasets()
    if max_examples:
        raw_data = raw_data[:max_examples]
    print(f"[finetune_us] {len(raw_data)} training examples loaded")

    texts = convert_dataset_to_instructions(raw_data, jurisdiction="US", template="llama3_chat")
    dataset = Dataset.from_dict({"text": texts})
    print(f"[finetune_us] Dataset formatted: {len(dataset)} examples")

    if dry_run:
        print("[finetune_us] Dry run complete — skipping model load and training")
        print(f"[finetune_us] Sample:\n{texts[0][:500]}...")
        return

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[finetune_us] Loading base model: {BASE_MODEL}")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        quantization_config=bnb_config,
        device_map="auto",
        attn_implementation="flash_attention_2",  # requires flash-attn package
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

    print("[finetune_us] Starting training...")
    trainer.train()

    print(f"[finetune_us] Saving adapter to {OUTPUT_DIR}")
    trainer.save_model(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
    print("[finetune_us] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QLoRA fine-tuning: US legal adapter")
    parser.add_argument("--dry-run", action="store_true", help="Load data only, skip training")
    parser.add_argument("--max-examples", type=int, default=None, help="Limit examples (smoke test)")
    parser.add_argument("--base-model", type=str, default=None, help="Override base model ID")
    args = parser.parse_args()

    if args.base_model:
        BASE_MODEL = args.base_model

    train(dry_run=args.dry_run, max_examples=args.max_examples)
