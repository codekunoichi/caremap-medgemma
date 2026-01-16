

from __future__ import annotations

from typing import Any, Dict

from .llm_client import MedGemmaClient
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_max_sentences,
    require_one_question,
)

LAB_OUT_KEYS = ["what_was_checked", "what_it_means", "what_to_ask_doctor"]


def interpret_lab(
    client: MedGemmaClient,
    test_name: str,
    meaning_category: str,
    source_note: str = "",
    prompt_file: str = "lab_prompt_v1.txt",
) -> Dict[str, Any]:
    """
    Generate one caregiver-friendly lab insight row.

    Inputs:
      - test_name: plain name for the lab/test
      - meaning_category: one of "Normal" / "Slightly off" / "Needs follow-up" (pre-computed)
      - source_note: optional non-numeric context from the record

    Returns JSON with keys:
      what_was_checked, what_it_means, what_to_ask_doctor
    """
    template = load_prompt(prompt_file)

    prompt = fill_prompt(
        template,
        {
            "TEST_NAME": (test_name or "").strip(),
            "MEANING_CATEGORY": (meaning_category or "").strip(),
            "SOURCE_NOTE": (source_note or "").strip(),
        },
    )

    raw = client.generate(prompt)
    obj = parse_json_strict(raw)

    # Strict schema
    require_exact_keys(obj, LAB_OUT_KEYS)

    # Constraints aligned to your input_output_rules.md
    require_max_sentences(obj.get("what_was_checked", ""), "what_was_checked", max_sentences=1)
    require_one_question(obj.get("what_to_ask_doctor", ""), "what_to_ask_doctor")

    return obj