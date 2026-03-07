"""Instruction format conversion for SFTTrainer fine-tuning.

Converts raw dataset entries into the instruction-tuning format
required by the QLoRA training pipeline.
"""

from typing import List


ALPACA_TEMPLATE = (
    "### Instruction:\n{instruction}\n\n"
    "### Input:\n{input}\n\n"
    "### Response:\n{output}"
)

LLAMA3_CHAT_TEMPLATE = (
    "<|begin_of_text|>"
    "<|start_header_id|>system<|end_header_id|>\n\n"
    "{instruction}<|eot_id|>"
    "<|start_header_id|>user<|end_header_id|>\n\n"
    "{input}<|eot_id|>"
    "<|start_header_id|>assistant<|end_header_id|>\n\n"
    "{output}<|eot_id|>"
)


def format_alpaca(instruction: str, input_text: str, output: str) -> str:
    return ALPACA_TEMPLATE.format(instruction=instruction, input=input_text, output=output)


def format_llama3_chat(instruction: str, input_text: str, output: str) -> str:
    return LLAMA3_CHAT_TEMPLATE.format(instruction=instruction, input=input_text, output=output)


def build_jp_instruction(question: str, answer: str) -> dict:
    return {
        "instruction": "You are a legal expert in Japanese corporate and securities law. Answer the following question with precise statutory citations.",
        "input_text": question,
        "output": answer,
    }


def build_us_instruction(question: str, answer: str) -> dict:
    return {
        "instruction": "You are a legal expert in US corporate and securities law. Answer the following question with precise case and statutory citations.",
        "input_text": question,
        "output": answer,
    }


def convert_dataset_to_instructions(
    raw_examples: List[dict],
    jurisdiction: str,
    template: str = "llama3_chat",
) -> List[str]:
    """Convert a list of raw Q&A pairs to formatted training strings."""
    formatter = format_llama3_chat if template == "llama3_chat" else format_alpaca
    builder = build_jp_instruction if jurisdiction == "JP" else build_us_instruction
    result = []
    for ex in raw_examples:
        instruction_dict = builder(ex.get("question", ""), ex.get("answer", ""))
        result.append(formatter(**instruction_dict))
    return result
