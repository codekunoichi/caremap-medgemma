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
    require_exact_keys(obj, IMAGING_OUT_KEYS)

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
        require_exact_keys(obj, IMAGING_OUT_KEYS)
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
