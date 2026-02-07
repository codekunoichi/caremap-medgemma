

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
    require_keys_with_defaults(obj, CARE_OUT_KEYS)

    # Keep action_item short and scannable
    require_max_sentences(obj.get("action_item", ""), "action_item", max_sentences=1)

    return obj


CARE_V2_OUT_KEYS = [
    "care_item",
    "time_bucket",
    "why_this_matters",
    "what_to_do",
    "how_to_prepare",
]


def interpret_caregap_v2_experimental(
    client: MedGemmaClient,
    item_text: str,
    next_step: str,
    time_bucket: str,
    source: str = "",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    EXPERIMENTAL: Unconstrained care gap interpretation.

    This version removes sentence limits to see what MedGemma
    can produce when given freedom to explain and empower caregivers.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails
    """
    template = load_prompt("caregap_prompt_v2_experimental.txt")

    prompt = fill_prompt(
        template,
        {
            "ITEM_TEXT": (item_text or "").strip(),
            "NEXT_STEP": (next_step or "").strip(),
            "TIME_BUCKET": (time_bucket or "").strip(),
            "SOURCE": (source or "").strip(),
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
        require_keys_with_defaults(obj, CARE_V2_OUT_KEYS)
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

    # Usage: PYTHONPATH=src .venv/bin/python -m caremap.caregap_interpretation

    # Load the golden patient complex data
    project_root = Path(__file__).parent.parent.parent
    golden_file = project_root / "examples" / "golden_patient_complex.json"

    print(f"Loading golden data from: {golden_file}")
    with open(golden_file) as f:
        golden_data = json.load(f)

    # Get the first care gap (INR recheck)
    gap = golden_data["care_gaps"][0]
    print(f"\n{'='*60}")
    print("INPUT (from golden_patient_complex.care_gaps[0]):")
    print(f"{'='*60}")
    print(f"item_text: {gap['item_text']}")
    print(f"next_step: {gap['next_step']}")
    print(f"time_bucket: {gap['time_bucket']}")
    print(f"source: {gap.get('source', '')}")

    # Initialize the MedGemma client
    print(f"\n{'='*60}")
    print("Initializing MedGemma client...")
    print(f"{'='*60}")
    client = MedGemmaClient()

    # Run V1 (constrained) interpretation
    print(f"\n{'='*60}")
    print("V1 CONSTRAINED (one-sentence limits):")
    print(f"{'='*60}")
    result_v1 = interpret_caregap(
        client=client,
        item_text=gap["item_text"],
        next_step=gap["next_step"],
        time_bucket=gap["time_bucket"],
    )
    print(json.dumps(result_v1, indent=2))

    # Run V2 (experimental, unconstrained) interpretation
    print(f"\n{'='*60}")
    print("V2 EXPERIMENTAL (no sentence limits):")
    print(f"{'='*60}")
    result_v2 = interpret_caregap_v2_experimental(
        client=client,
        item_text=gap["item_text"],
        next_step=gap["next_step"],
        time_bucket=gap["time_bucket"],
        source=gap.get("source", ""),
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