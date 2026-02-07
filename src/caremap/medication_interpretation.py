

from __future__ import annotations

from typing import Any, Dict

from .llm_client import MedGemmaClient
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_keys_with_defaults,
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


MED_V2_OUT_KEYS = ["medication", "what_this_does", "how_to_give", "watch_out_for"]


def interpret_medication_v2_experimental(
    client: MedGemmaClient,
    medication_name: str,
    when_to_give: str,
    clinician_notes: str = "",
    interaction_notes: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    EXPERIMENTAL: Unconstrained medication interpretation.

    This version removes the one-sentence limits to see what MedGemma
    can actually produce when given freedom to explain and simplify.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails
    """
    template = load_prompt("medication_prompt_v2_experimental.txt")

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

    if debug:
        print(f"\n{'='*60}")
        print("RAW MEDGEMMA OUTPUT:")
        print(f"{'='*60}")
        print(raw)
        print(f"{'='*60}")

    try:
        obj = parse_json_strict(raw)
        # Strict schema (but no sentence limits!)
        require_exact_keys(obj, MED_V2_OUT_KEYS)
        return obj
    except Exception as e:
        if debug:
            print(f"\nJSON parsing failed: {e}")
            print("Returning raw output as 'raw_response' field")
            return {"raw_response": raw, "error": str(e)}
        raise


MED_V3_OUT_KEYS = ["medication", "what_this_does", "how_to_give", "watch_out_for"]


def interpret_medication_v3_grounded(
    client: MedGemmaClient,
    medication_name: str,
    sig_text: str,
    clinician_notes: str = "",
    interaction_notes: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    V3 GROUNDED: Chain-of-thought prompting with explicit reasoning.

    This version uses few-shot examples and asks the model to reason
    step-by-step before generating JSON, which may improve grounding
    and reduce hallucination.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails
    """
    template = load_prompt("medication_prompt_v3_grounded.txt")

    prompt = fill_prompt(
        template,
        {
            "MEDICATION_NAME": (medication_name or "").strip(),
            "SIG_TEXT": (sig_text or "").strip(),
            "CLINICIAN_NOTES": (clinician_notes or "").strip(),
            "INTERACTION_NOTES": (interaction_notes or "").strip(),
        },
    )

    raw = client.generate(prompt)

    if debug:
        print(f"\n{'='*60}")
        print("RAW MEDGEMMA OUTPUT (includes reasoning):")
        print(f"{'='*60}")
        print(raw)
        print(f"{'='*60}")

    try:
        obj = parse_json_strict(raw)
        # Lenient schema: fill missing keys with safe default
        require_keys_with_defaults(obj, MED_V3_OUT_KEYS)
        return obj, raw  # Return both parsed JSON and raw (for reasoning)
    except Exception as e:
        if debug:
            print(f"\nJSON parsing failed: {e}")
            print("Returning raw output as 'raw_response' field")
            return {"raw_response": raw, "error": str(e)}, raw
        raise


if __name__ == "__main__":
    import json
    from pathlib import Path

    # Usage: PYTHONPATH=src .venv/bin/python -m caremap.medication_interpretation

    # Load the golden patient complex data
    project_root = Path(__file__).parent.parent.parent
    golden_file = project_root / "examples" / "golden_patient_complex.json"

    print(f"Loading golden data from: {golden_file}")
    with open(golden_file) as f:
        golden_data = json.load(f)

    # Get the first medication
    med = golden_data["medications"][0]
    print(f"\n{'='*60}")
    print("INPUT (from golden_patient_complex.medications[0]):")
    print(f"{'='*60}")
    print(f"medication_name: {med['medication_name']}")
    print(f"sig_text: {med['sig_text']}")
    print(f"clinician_notes: {med['clinician_notes']}")
    print(f"interaction_notes: {med['interaction_notes']}")

    # Initialize the MedGemma client
    print(f"\n{'='*60}")
    print("Initializing MedGemma client...")
    print(f"{'='*60}")
    client = MedGemmaClient()

    # Run V1 (constrained) interpretation
    print(f"\n{'='*60}")
    print("V1 CONSTRAINED (one-sentence limits):")
    print(f"{'='*60}")
    result_v1 = interpret_medication(
        client=client,
        medication_name=med["medication_name"],
        when_to_give=med["sig_text"],
        clinician_notes=med["clinician_notes"],
        interaction_notes=med["interaction_notes"],
    )
    print(json.dumps(result_v1, indent=2))

    # Run V2 (experimental, unconstrained) interpretation
    print(f"\n{'='*60}")
    print("V2 EXPERIMENTAL (no sentence limits):")
    print(f"{'='*60}")
    result_v2 = interpret_medication_v2_experimental(
        client=client,
        medication_name=med["medication_name"],
        when_to_give=med["sig_text"],
        clinician_notes=med["clinician_notes"],
        interaction_notes=med["interaction_notes"],
    )
    print(json.dumps(result_v2, indent=2))

    # Run V3 (grounded, chain-of-thought) interpretation
    print(f"\n{'='*60}")
    print("V3 GROUNDED (chain-of-thought with reasoning):")
    print(f"{'='*60}")
    result_v3, raw_v3 = interpret_medication_v3_grounded(
        client=client,
        medication_name=med["medication_name"],
        sig_text=med["sig_text"],
        clinician_notes=med["clinician_notes"],
        interaction_notes=med["interaction_notes"],
        debug=True,
    )
    if "raw_response" not in result_v3:
        print("\nPARSED JSON:")
        print(json.dumps(result_v3, indent=2))

    # Summary comparison
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY:")
    print(f"{'='*60}")

    v1_safety = result_v1.get('important_note', '')
    v2_safety = result_v2.get('watch_out_for', '')
    v3_safety = result_v3.get('watch_out_for', '') if "raw_response" not in result_v3 else ""

    print(f"{'Field':<25} {'V1':<10} {'V2':<10} {'V3':<10}")
    print("-" * 55)
    print(f"{'Safety info length':<25} {len(v1_safety):<10} {len(v2_safety):<10} {len(v3_safety):<10}")

    print(f"\nKidney warning included:")
    print(f"  V1: {'YES' if 'kidney' in v1_safety.lower() else 'NO (DROPPED)'}")
    print(f"  V2: {'YES' if 'kidney' in v2_safety.lower() else 'NO'}")
    print(f"  V3: {'YES' if 'kidney' in v3_safety.lower() else 'NO'}")

    print(f"\nCT scan warning included:")
    print(f"  V1: {'YES' if 'ct' in v1_safety.lower() or 'scan' in v1_safety.lower() else 'NO'}")
    print(f"  V2: {'YES' if 'ct' in v2_safety.lower() or 'scan' in v2_safety.lower() else 'NO'}")
    print(f"  V3: {'YES' if 'ct' in v3_safety.lower() or 'scan' in v3_safety.lower() else 'NO'}")