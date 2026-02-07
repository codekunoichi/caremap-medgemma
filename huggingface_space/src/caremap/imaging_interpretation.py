"""
Imaging interpretation module for CareMap.

Provides caregiver-friendly explanations of medical imaging reports
(CT, MRI, X-ray) using MedGemma's multimodal capabilities.

Safety Rules:
- No diagnosis language
- No treatment recommendations
- Plain language only (6th grade reading level)
- Always defer to clinician for interpretation
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path

from .llm_client import MedGemmaClient, IMAGING_SYSTEM_PROMPT
from .prompt_loader import fill_prompt, load_prompt
from .validators import (
    parse_json_strict,
    require_exact_keys,
    require_keys_with_defaults,
    require_max_sentences,
    require_one_question,
)

IMAGING_OUT_KEYS = ["study_type", "what_was_done", "key_finding", "what_to_ask_doctor"]


def interpret_imaging_report(
    client: MedGemmaClient,
    study_type: str,
    report_text: str,
    flag: str = "normal",
    prompt_file: str = "imaging_prompt_v1.txt",
) -> Dict[str, Any]:
    """
    Generate a caregiver-friendly summary of an imaging report (text-only mode).

    This uses the radiology report text, NOT the actual images.
    For multimodal image interpretation, use interpret_imaging_with_image().

    Inputs:
      - study_type: Type of study (e.g., "Chest CT", "Brain MRI", "Chest X-ray")
      - report_text: The radiology report text (impression/findings)
      - flag: Qualitative status (normal, needs_follow_up, urgent)

    Returns JSON with keys:
      study_type, what_was_done, key_finding, what_to_ask_doctor
    """
    template = load_prompt(prompt_file)

    prompt = fill_prompt(
        template,
        {
            "STUDY_TYPE": (study_type or "").strip(),
            "REPORT_TEXT": (report_text or "").strip(),
            "FLAG": (flag or "normal").strip(),
        },
    )

    raw = client.generate(prompt)
    obj = parse_json_strict(raw)

    # Strict schema validation
    require_keys_with_defaults(obj, IMAGING_OUT_KEYS)

    # Safety constraints
    # Note: Golden specs allow 2-3 sentences for key_finding in imaging reports
    require_max_sentences(obj.get("what_was_done", ""), "what_was_done", max_sentences=1)
    require_max_sentences(obj.get("key_finding", ""), "key_finding", max_sentences=3)
    require_one_question(obj.get("what_to_ask_doctor", ""), "what_to_ask_doctor")

    return obj


def interpret_imaging_with_image(
    client: MedGemmaClient,
    study_type: str,
    image_paths: List[str],
    report_text: str = "",
    flag: str = "normal",
) -> Dict[str, Any]:
    """
    Generate a caregiver-friendly summary using actual medical images (multimodal mode).

    This requires MedGemma's multimodal pipeline and actual image files.
    Initialize MedGemmaClient with enable_multimodal=True for full functionality.

    Inputs:
      - study_type: Type of study (e.g., "Chest CT", "Brain MRI")
      - image_paths: List of paths to image files (slices for CT/MRI)
      - report_text: Optional radiology report text (fallback to text-only mode)
      - flag: Qualitative status (normal, needs_follow_up, urgent)

    Returns JSON with keys:
      study_type, what_was_done, key_finding, what_to_ask_doctor
    """
    # Validate image paths exist
    for path in image_paths:
        if not Path(path).exists():
            raise FileNotFoundError(f"Image not found: {path}")

    # If report text available, prefer text-only interpretation (more reliable)
    if report_text:
        return interpret_imaging_report(
            client=client,
            study_type=study_type,
            report_text=report_text,
            flag=flag,
        )

    # Use multimodal if client supports it
    if client.supports_multimodal:
        plain_study = get_plain_study_type(study_type)

        # Build prompt for multimodal interpretation
        prompt = f"""Look at this {plain_study} image.

Describe what you see in plain language for a family caregiver.

Respond with a JSON object containing exactly these four keys:
- study_type: "{study_type}" (copy exactly)
- what_was_done: ONE sentence explaining what this scan shows (plain language)
- key_finding: Up to TWO sentences describing what you see (no diagnosis, no medical terms)
- what_to_ask_doctor: ONE question the caregiver should ask their doctor

The flag for this result is: {flag}
"""

        raw = client.generate_with_images(
            prompt=prompt,
            images=image_paths,
            system_prompt=IMAGING_SYSTEM_PROMPT,
        )

        obj = parse_json_strict(raw)

        # Validate output
        require_keys_with_defaults(obj, IMAGING_OUT_KEYS)
        require_max_sentences(obj.get("what_was_done", ""), "what_was_done", max_sentences=1)
        require_max_sentences(obj.get("key_finding", ""), "key_finding", max_sentences=3)
        require_one_question(obj.get("what_to_ask_doctor", ""), "what_to_ask_doctor")

        return obj

    # Fallback: no report text and no multimodal support
    return {
        "study_type": study_type,
        "what_was_done": f"A {study_type} scan was performed.",
        "key_finding": "Please ask your doctor to explain the imaging results.",
        "what_to_ask_doctor": "What did my imaging study show?",
    }


# Mapping of common study types to plain language
STUDY_TYPE_PLAIN_LANGUAGE = {
    "CT": "CT scan (detailed X-ray pictures)",
    "MRI": "MRI scan (detailed pictures using magnets)",
    "X-ray": "X-ray picture",
    "Chest CT": "CT scan of the chest",
    "Brain MRI": "MRI scan of the brain",
    "Abdominal CT": "CT scan of the belly area",
    "Chest X-ray": "X-ray of the chest",
    "Mammogram": "Breast X-ray",
    "Ultrasound": "Ultrasound (sound wave pictures)",
    "PET scan": "PET scan (shows how organs are working)",
}


def get_plain_study_type(study_type: str) -> str:
    """Convert medical study type to plain language."""
    normalized = study_type.strip()
    return STUDY_TYPE_PLAIN_LANGUAGE.get(normalized, f"{normalized} scan")


IMAGING_V2_OUT_KEYS = [
    "study_type",
    "what_this_scan_does",
    "what_was_found",
    "what_this_means",
    "questions_for_doctor",
]


def interpret_imaging_v2_experimental(
    client: MedGemmaClient,
    study_type: str,
    report_text: str,
    flag: str = "normal",
    debug: bool = False,
) -> Dict[str, Any]:
    """
    EXPERIMENTAL: Unconstrained imaging interpretation.

    This version removes sentence limits to see what MedGemma
    can produce when given freedom to explain and translate medical imaging.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails
    """
    template = load_prompt("imaging_prompt_v2_experimental.txt")

    prompt = fill_prompt(
        template,
        {
            "STUDY_TYPE": (study_type or "").strip(),
            "REPORT_TEXT": (report_text or "").strip(),
            "FLAG": (flag or "normal").strip(),
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
        require_keys_with_defaults(obj, IMAGING_V2_OUT_KEYS)
        return obj
    except Exception as e:
        if debug:
            print(f"\nJSON parsing failed: {e}")
            print("Returning raw output as 'raw_response' field")
            return {"raw_response": raw, "error": str(e)}
        raise


IMAGING_V3_OUT_KEYS = [
    "study_type",
    "what_this_scan_does",
    "what_was_found",
    "what_this_means",
    "questions_for_doctor",
]


def interpret_imaging_v3_grounded(
    client: MedGemmaClient,
    study_type: str,
    report_text: str,
    flag: str = "normal",
    debug: bool = False,
) -> tuple:
    """
    V3 GROUNDED: Chain-of-thought prompting with explicit reasoning.

    This version uses few-shot examples and asks the model to reason
    step-by-step before generating JSON, which may improve grounding
    and reduce hallucination.

    Args:
        debug: If True, print raw output and return it even if JSON parsing fails

    Returns:
        tuple: (parsed_json, raw_output)
    """
    template = load_prompt("imaging_prompt_v3_grounded.txt")

    prompt = fill_prompt(
        template,
        {
            "STUDY_TYPE": (study_type or "").strip(),
            "REPORT_TEXT": (report_text or "").strip(),
            "FLAG": (flag or "normal").strip(),
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
        # Strict schema (same as V2)
        require_keys_with_defaults(obj, IMAGING_V3_OUT_KEYS)
        return obj, raw
    except Exception as e:
        if debug:
            print(f"\nJSON parsing failed: {e}")
            print("Returning raw output as 'raw_response' field")
            return {"raw_response": raw, "error": str(e)}, raw
        raise


if __name__ == "__main__":
    import json
    from pathlib import Path

    # Usage: PYTHONPATH=src .venv/bin/python -m caremap.imaging_interpretation

    # Sample imaging report (since golden_patient_complex doesn't have imaging)
    sample_study = {
        "study_type": "Chest CT",
        "report_text": """IMPRESSION:
1. 8mm ground-glass nodule in the right lower lobe, recommend follow-up CT in 3 months.
2. Mild cardiomegaly with trace pericardial effusion.
3. Atherosclerotic calcifications of the coronary arteries and thoracic aorta.
4. No pleural effusion or pneumothorax.""",
        "flag": "needs_follow_up",
    }

    print(f"{'='*60}")
    print("INPUT (sample imaging report):")
    print(f"{'='*60}")
    print(f"study_type: {sample_study['study_type']}")
    print(f"flag: {sample_study['flag']}")
    print(f"report_text:\n{sample_study['report_text']}")

    # Initialize the MedGemma client
    print(f"\n{'='*60}")
    print("Initializing MedGemma client...")
    print(f"{'='*60}")

    client = MedGemmaClient()

    # Run V1 (constrained) interpretation
    print(f"\n{'='*60}")
    print("V1 CONSTRAINED (sentence limits):")
    print(f"{'='*60}")
    result_v1 = interpret_imaging_report(
        client=client,
        study_type=sample_study["study_type"],
        report_text=sample_study["report_text"],
        flag=sample_study["flag"],
    )
    print(json.dumps(result_v1, indent=2))

    # Run V2 (experimental, unconstrained) interpretation
    print(f"\n{'='*60}")
    print("V2 EXPERIMENTAL (no sentence limits):")
    print(f"{'='*60}")
    result_v2 = interpret_imaging_v2_experimental(
        client=client,
        study_type=sample_study["study_type"],
        report_text=sample_study["report_text"],
        flag=sample_study["flag"],
        debug=False,
    )
    if "raw_response" not in result_v2:
        print(json.dumps(result_v2, indent=2))

    # Run V3 (grounded, chain-of-thought) interpretation
    print(f"\n{'='*60}")
    print("V3 GROUNDED (chain-of-thought with reasoning):")
    print(f"{'='*60}")
    result_v3, raw_v3 = interpret_imaging_v3_grounded(
        client=client,
        study_type=sample_study["study_type"],
        report_text=sample_study["report_text"],
        flag=sample_study["flag"],
        debug=True,
    )
    if "raw_response" not in result_v3:
        print("\nPARSED JSON:")
        print(json.dumps(result_v3, indent=2))

    # Summary comparison
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY:")
    print(f"{'='*60}")

    v1_total = sum(len(str(v)) for v in result_v1.values())
    v2_total = sum(len(str(v)) for v in result_v2.values()) if "raw_response" not in result_v2 else 0
    v3_total = sum(len(str(v)) for v in result_v3.values()) if "raw_response" not in result_v3 else 0

    print(f"{'Metric':<30} {'V1':<10} {'V2':<10} {'V3':<10}")
    print("-" * 60)
    print(f"{'Total content (chars)':<30} {v1_total:<10} {v2_total:<10} {v3_total:<10}")

    # Check for forbidden terms
    def has_forbidden(obj):
        text = " ".join(str(v) for v in obj.values()).lower()
        forbidden = ["nodule", "lesion", "mm", "effusion", "cardiomegaly", "atherosclerotic"]
        return [f for f in forbidden if f in text]

    v1_forbidden = has_forbidden(result_v1)
    v2_forbidden = has_forbidden(result_v2) if "raw_response" not in result_v2 else []
    v3_forbidden = has_forbidden(result_v3) if "raw_response" not in result_v3 else []

    print(f"\n{'Forbidden medical terms found:'}")
    print(f"  V1: {v1_forbidden if v1_forbidden else 'None ✓'}")
    print(f"  V2: {v2_forbidden if v2_forbidden else 'None ✓'}")
    print(f"  V3: {v3_forbidden if v3_forbidden else 'None ✓'}")
