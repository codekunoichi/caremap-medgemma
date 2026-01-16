

from __future__ import annotations

from typing import Any, Dict

from .llm_client import MedGemmaClient
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_max_sentences,
)

MED_OUT_KEYS = ["medication", "why_it_matters", "when_to_give", "important_note"]


def interpret_medication(
    client: MedGemmaClient,
    medication_name: str,
    when_to_give: str,
    clinician_notes: str = "",
    interaction_notes: str = "",
    prompt_file: str = "medication_prompt_v1.txt",
) -> Dict[str, Any]:
    """
    Generate one caregiver-friendly medication row.

    Inputs:
      - medication_name: normalized name
      - when_to_give: dosage + frequency + timing from EHR (required for fridge sheet clarity)
      - clinician_notes: optional safety/handling notes from source record
      - interaction_notes: optional VERIFIED interaction notes (no speculation)

    Returns JSON with keys:
      medication, why_it_matters, when_to_give, important_note
    """
    template = load_prompt(prompt_file)

    prompt = fill_prompt(
        template,
        {
            "MEDICATION_NAME": (medication_name or "").strip(),
            "WHEN_TO_GIVE": (when_to_give or "").strip(),
            "CLINICIAN_NOTES": (clinician_notes or "").strip(),
            "INTERACTION_NOTES": (interaction_notes or "").strip(),
        },
    )

    raw = client.generate(prompt)
    obj = parse_json_strict(raw)

    # Strict schema
    require_exact_keys(obj, MED_OUT_KEYS)

    # Style/safety constraints
    require_max_sentences(obj.get("why_it_matters", ""), "why_it_matters", max_sentences=1)
    require_max_sentences(obj.get("important_note", ""), "important_note", max_sentences=1)

    return obj