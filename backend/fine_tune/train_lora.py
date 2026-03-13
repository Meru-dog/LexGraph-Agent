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


def train(
    base_model: str = "NousResearch/Meta-Llama-3.1-8B-Instruct",
    data_path: str = "fine_tune/data/legal_qa.jsonl",
    output_dir: str = "fine_tune/adapters/lexgraph-legal",
    epochs: int = 3,
    batch_size: int = 1,
    learning_rate: float = 2e-4,
    max_seq_length: int = 512,
):
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
        from peft import LoraConfig, get_peft_model, TaskType
        from trl import SFTTrainer
        from datasets import Dataset
    except ImportError as e:
        raise SystemExit(
            f"Missing fine-tuning deps: {e}\n"
            "Run: pip install transformers peft bitsandbytes datasets accelerate trl"
        )

    device = _detect_device()
    print(f"Device: {device}")

    print(f"Loading dataset from {data_path}...")
    raw = load_dataset_from_jsonl(data_path)
    texts = [format_prompt(ex) for ex in raw]
    dataset = Dataset.from_dict({"text": texts})

    print(f"Loading base model: {base_model}")
    # Mac MPS/CPU: load in float16 (bitsandbytes 4-bit not supported on Apple Silicon)
    dtype = torch.float16
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=dtype,
        device_map={"": device},
        trust_remote_code=True,
    )
    model.config.use_cache = False
    model.enable_input_require_grads()

    lora_config = LoraConfig(
        r=8,                    # lower rank = less memory
        lora_alpha=16,
        target_modules=["q_proj", "v_proj"],   # fewer modules = less memory
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=8,   # effective batch = 8
        gradient_checkpointing=True,     # saves memory
        warmup_steps=5,
        learning_rate=learning_rate,
        fp16=False,                      # MPS doesn't support fp16 training
        bf16=False,
        logging_steps=1,
        save_strategy="epoch",
        optim="adamw_torch",             # paged_adamw_8bit requires CUDA
        report_to="none",
        use_mps_device=(device == "mps"),
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
        max_seq_length=max_seq_length,
        dataset_text_field="text",
        packing=False,
    )

    print("Starting training...")
    trainer.train()
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"\nAdapter saved to {output_dir}")
    print("\nNext step: merge & export to GGUF for Ollama:")
    print(f"  python fine_tune/export_gguf.py --adapter {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Llama 3.1 8B for LexGraph Legal")
    # NousResearch mirror is not gated — no HuggingFace approval needed
    # Alternative: meta-llama/Llama-3.1-8B-Instruct (requires HF access request)
    parser.add_argument("--base_model", default="NousResearch/Meta-Llama-3.1-8B-Instruct")
    parser.add_argument("--data_path", default="fine_tune/data/legal_qa.jsonl")
    parser.add_argument("--output_dir", default="fine_tune/adapters/lexgraph-legal")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    args = parser.parse_args()
    train(
        base_model=args.base_model,
        data_path=args.data_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
