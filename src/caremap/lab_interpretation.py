

from __future__ import annotations

from typing import Any, Dict

from .llm_client import MedGemmaClient
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_keys_with_defaults,
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
    require_keys_with_defaults(obj, LAB_OUT_KEYS)

    # Constraints aligned to your input_output_rules.md
    require_max_sentences(obj.get("what_was_checked", ""), "what_was_checked", max_sentences=1)
    require_one_question(obj.get("what_to_ask_doctor", ""), "what_to_ask_doctor")

    return obj


LAB_V2_OUT_KEYS = [
    "test_name",
    "what_this_test_measures",
    "why_this_matters",
    "current_status",
    "questions_for_doctor",
]


def interpret_lab_v2_experimental(
    client: MedGemmaClient,
    test_name: str,
    meaning_category: str,
    source_note: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    EXPERIMENTAL: Unconstrained lab interpretation.

    This version removes sentence limits to see what MedGemma
    can produce when given freedom to explain and educate.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails
    """
    template = load_prompt("lab_prompt_v2_experimental.txt")

    prompt = fill_prompt(
        template,
        {
            "TEST_NAME": (test_name or "").strip(),
            "MEANING_CATEGORY": (meaning_category or "").strip(),
            "SOURCE_NOTE": (source_note or "").strip(),
        },
    )

    raw = client.generate(prompt)

    if debug:
        print(f"\n{'='*60}")
        print("RAW MEDGEMMA OUTPUT:")
        print(f"{'='*60}")
        print(raw)
        print(f"{'='*60}")

    try:
        obj = parse_json_strict(raw)
        # Strict schema (but no sentence limits!)
        require_keys_with_defaults(obj, LAB_V2_OUT_KEYS)
        return obj
    except Exception as e:
        if debug:
            print(f"\nJSON parsing failed: {e}")
            print("Returning raw output as 'raw_response' field")
            return {"raw_response": raw, "error": str(e)}
        raise


if __name__ == "__main__":
    import json
    from pathlib import Path

    # Usage: PYTHONPATH=src .venv/bin/python -m caremap.lab_interpretation

    # Load the golden patient complex data
    project_root = Path(__file__).parent.parent.parent
    golden_file = project_root / "examples" / "golden_patient_complex.json"

    print(f"Loading golden data from: {golden_file}")
    with open(golden_file) as f:
        golden_data = json.load(f)

    # Get the first lab result (INR)
    lab = golden_data["results"][0]
    print(f"\n{'='*60}")
    print("INPUT (from golden_patient_complex.results[0]):")
    print(f"{'='*60}")
    print(f"test_name: {lab['test_name']}")
    print(f"meaning_category: {lab['meaning_category']}")
    print(f"source_note: {lab['source_note']}")

    # Initialize the MedGemma client
    print(f"\n{'='*60}")
    print("Initializing MedGemma client...")
    print(f"{'='*60}")
    client = MedGemmaClient()

    # Run V1 (constrained) interpretation
    print(f"\n{'='*60}")
    print("V1 CONSTRAINED (one-sentence limits):")
    print(f"{'='*60}")
    result_v1 = interpret_lab(
        client=client,
        test_name=lab["test_name"],
        meaning_category=lab["meaning_category"],
        source_note=lab["source_note"],
    )
    print(json.dumps(result_v1, indent=2))

    # Run V2 (experimental, unconstrained) interpretation
    print(f"\n{'='*60}")
    print("V2 EXPERIMENTAL (no sentence limits):")
    print(f"{'='*60}")
    result_v2 = interpret_lab_v2_experimental(
        client=client,
        test_name=lab["test_name"],
        meaning_category=lab["meaning_category"],
        source_note=lab["source_note"],
    )
    print(json.dumps(result_v2, indent=2))

    # Summary comparison
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY:")
    print(f"{'='*60}")
    v1_total = sum(len(str(v)) for v in result_v1.values())
    v2_total = sum(len(str(v)) for v in result_v2.values())
    print(f"V1 total content: {v1_total} chars")
    print(f"V2 total content: {v2_total} chars")
    print(f"V2 provides {v2_total / v1_total:.1f}x more information")