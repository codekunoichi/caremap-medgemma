

from __future__ import annotations

from typing import Any, Dict

from .llm_client import MedGemmaClient
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_max_sentences,
)

CARE_OUT_KEYS = ["time_bucket", "action_item", "next_step"]


def interpret_caregap(
    client: MedGemmaClient,
    item_text: str,
    next_step: str,
    time_bucket: str,
    prompt_file: str = "caregap_prompt_v1.txt",
) -> Dict[str, Any]:
    """
    Generate one caregiver-friendly follow-up action row.

    Inputs:
      - item_text: plain description of the overdue/missing item
      - next_step: concrete instruction from the source record
      - time_bucket: one of "Today" / "This Week" / "Later" (pre-assigned)

    Returns JSON with keys:
      time_bucket, action_item, next_step
    """
    template = load_prompt(prompt_file)

    prompt = fill_prompt(
        template,
        {
            "ITEM_TEXT": (item_text or "").strip(),
            "NEXT_STEP": (next_step or "").strip(),
            "TIME_BUCKET": (time_bucket or "").strip(),
        },
    )

    raw = client.generate(prompt)
    obj = parse_json_strict(raw)

    # Strict schema
    require_exact_keys(obj, CARE_OUT_KEYS)

    # Keep action_item short and scannable
    require_max_sentences(obj.get("action_item", ""), "action_item", max_sentences=1)

    return obj