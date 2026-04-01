"""Export LoRA-merged model to GGUF format for Ollama.

Steps:
  1. Merge LoRA adapter into base model
  2. Save merged weights as safetensors
  3. Convert to GGUF using llama.cpp convert script
  4. Quantize with llama.cpp quantize (Q4_K_M recommended)
  5. Create Ollama Modelfile and import

Usage:
    python fine_tune/export_gguf.py \
        --base_model meta-llama/Llama-3.1-8B-Instruct \
        --adapter fine_tune/adapters/lexgraph-legal \
        --output_dir fine_tune/gguf \
        --quant Q4_K_M
"""

import argparse
import os
import subprocess
import sys


def export(
    base_model: str,
    adapter_dir: str,
    output_dir: str,
    quant: str = "Q4_K_M",
    llama_cpp_dir: str = "./llama.cpp",
):
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
    except ImportError as e:
        raise SystemExit(f"Missing deps: {e}\nRun: pip install transformers peft")

    # ── W&B run ───────────────────────────────────────────────────────────────
    _wandb_run = None
    try:
        import wandb, time
        _wandb_run = wandb.init(
            project="lexgraph-finetune",
            job_type="export",
            name=f"export-gguf-{quant}-{int(time.time())}",
            config={
                "base_model":   base_model,
                "adapter_dir":  adapter_dir,
                "quant":        quant,
                "llama_cpp_dir": llama_cpp_dir,
            },
        )
        print(f"[wandb] Export run: {_wandb_run.url}")
    except Exception as e:
        print(f"[wandb] init skipped (non-fatal): {e}")

    os.makedirs(output_dir, exist_ok=True)
    merged_dir = os.path.join(output_dir, "merged")

    print("Merging LoRA adapter into base model...")
    base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float16, device_map="cpu")
    model = PeftModel.from_pretrained(base, adapter_dir)
    model = model.merge_and_unload()
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    model.save_pretrained(merged_dir)
    tokenizer.save_pretrained(merged_dir)
    print(f"Merged model saved to {merged_dir}")

    gguf_path = os.path.join(output_dir, "lexgraph-legal.gguf")
    convert_script = os.path.join(llama_cpp_dir, "convert_hf_to_gguf.py")
    if not os.path.exists(convert_script):
        print(f"llama.cpp not found at {llama_cpp_dir}.")
        print("Clone it: git clone https://github.com/ggerganov/llama.cpp")
        print(f"Then run: python {convert_script} {merged_dir} --outfile {gguf_path} --outtype f16")
        return

    print("Converting to GGUF...")
    subprocess.run([sys.executable, convert_script, merged_dir, "--outfile", gguf_path, "--outtype", "f16"], check=True)

    quant_path = os.path.join(output_dir, f"lexgraph-legal-{quant}.gguf")
    quantize_bin = os.path.join(llama_cpp_dir, "build", "bin", "llama-quantize")
    if os.path.exists(quantize_bin):
        print(f"Quantizing to {quant}...")
        subprocess.run([quantize_bin, gguf_path, quant_path, quant], check=True)
        final_gguf = quant_path
    else:
        print(f"Quantize binary not found — using unquantized f16 model.")
        final_gguf = gguf_path

    # Write Ollama Modelfile
    modelfile_path = os.path.join(output_dir, "Modelfile")
    with open(modelfile_path, "w") as f:
        f.write(f"""FROM {final_gguf}

PARAMETER temperature 0.1
PARAMETER num_predict 2048
PARAMETER top_k 40
PARAMETER top_p 0.9

SYSTEM \"\"\"
You are LexGraph Legal, an expert AI assistant specializing in:
- Japanese corporate law (会社法, 金商法, 民法)
- US securities law (Securities Act, Exchange Act, Dodd-Frank)
- M&A due diligence (JP/US dual jurisdiction)
- Contract drafting and review
- Legal risk assessment and compliance

Respond concisely and accurately. When citing law, include article numbers.
Support both Japanese and English responses.
\"\"\"
""")
    print(f"Modelfile written to {modelfile_path}")
    print(f"\nTo import into Ollama:")
    print(f"  ollama create lexgraph-legal -f {modelfile_path}")
    print(f"  ollama run lexgraph-legal")

    # ── W&B: log GGUF artifact + file size metrics ────────────────────────────
    if _wandb_run:
        try:
            import wandb
            gguf_size_mb = round(os.path.getsize(final_gguf) / 1e6, 1) if os.path.exists(final_gguf) else 0
            wandb.log({
                "export/gguf_size_mb": gguf_size_mb,
                "export/quantized":    final_gguf == quant_path,
            })
            artifact = wandb.Artifact(
                name="lexgraph-gguf",
                type="model",
                description=f"GGUF export ({quant}) of {base_model} + LoRA adapter",
                metadata={
                    "base_model":   base_model,
                    "quant":        quant,
                    "gguf_size_mb": gguf_size_mb,
                    "adapter_dir":  adapter_dir,
                },
            )
            artifact.add_file(final_gguf)
            artifact.add_file(modelfile_path)
            _wandb_run.log_artifact(artifact)
            _wandb_run.finish()
            print(f"[wandb] GGUF artifact logged ({gguf_size_mb} MB)")
        except Exception as e:
            print(f"[wandb] artifact log error (non-fatal): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--adapter", default="fine_tune/adapters/lexgraph-legal")
    parser.add_argument("--output_dir", default="fine_tune/gguf")
    parser.add_argument("--quant", default="Q4_K_M")
    parser.add_argument("--llama_cpp_dir", default="./llama.cpp")
    args = parser.parse_args()
    export(args.base_model, args.adapter, args.output_dir, args.quant, args.llama_cpp_dir)
