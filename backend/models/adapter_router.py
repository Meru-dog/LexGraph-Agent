"""adapter_router — select JP or US QLoRA adapter based on jurisdiction.

Phase 4: routes to adapter_jp/ or adapter_us/ LoRA weights.
"""

import os
from typing import Literal

ADAPTER_JP_PATH = os.getenv("ADAPTER_JP_PATH", "./adapters/adapter_jp")
ADAPTER_US_PATH = os.getenv("ADAPTER_US_PATH", "./adapters/adapter_us")


def select_adapter(jurisdiction: str) -> Literal["jp", "us"]:
    """Return the appropriate adapter identifier for a given jurisdiction."""
    if jurisdiction in ("JP", "jp", "ja"):
        return "jp"
    return "us"


def load_adapter(adapter_id: Literal["jp", "us"]):
    """Load a QLoRA adapter into the base model.

    Phase 4: implement with peft PeftModel.
    """
    # TODO Phase 4:
    # from peft import PeftModel
    # base_model = load_base_model()
    # path = ADAPTER_JP_PATH if adapter_id == "jp" else ADAPTER_US_PATH
    # return PeftModel.from_pretrained(base_model, path)
    raise NotImplementedError("Adapter loading available in Phase 4")
