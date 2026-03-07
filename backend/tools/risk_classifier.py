"""risk_classifier — legal risk scoring via fine-tuned LLaMA (QLoRA adapter)."""

from typing import Literal

RiskLevel = Literal["critical", "high", "medium", "low"]


def risk_classifier(text: str, context: str) -> RiskLevel:
    """Score legal risk level for a text excerpt.

    Phase 2 stub — returns heuristic score.
    Phase 4: route to fine-tuned LLaMA via adapter_router.
    """
    # TODO Phase 4: use fine-tuned LLaMA for risk classification
    # from models.llama_client import llama_client
    # from models.adapter_router import select_adapter
    # adapter = select_adapter(context)
    # return llama_client.classify_risk(text, context, adapter=adapter)
    keywords_critical = ["undisclosed", "violation", "criminal", "fraud"]
    keywords_high = ["going concern", "concentration", "unlicensed", "non-compliance"]
    keywords_medium = ["overtime", "underpayment", "change of control", "ip license"]
    lower = (text + " " + context).lower()
    if any(k in lower for k in keywords_critical):
        return "critical"
    if any(k in lower for k in keywords_high):
        return "high"
    if any(k in lower for k in keywords_medium):
        return "medium"
    return "low"
