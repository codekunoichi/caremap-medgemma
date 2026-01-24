"""
Scenario loader for CareMap golden specification tests.

Loads golden spec JSON files and provides helper functions to
extract test scenarios with their inputs and expected validations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_examples_dir() -> Path:
    """Get the path to the examples directory."""
    # Try relative to this file
    tests_dir = Path(__file__).parent.parent
    project_root = tests_dir.parent
    examples_dir = project_root / "examples"

    if examples_dir.exists():
        return examples_dir

    raise FileNotFoundError(f"Examples directory not found at {examples_dir}")


def load_golden_spec(filename: str) -> Dict[str, Any]:
    """
    Load a golden specification JSON file.

    Args:
        filename: Name of the file in examples/ directory

    Returns:
        Parsed JSON as dictionary
    """
    filepath = get_examples_dir() / filename
    with open(filepath) as f:
        return json.load(f)


def get_lab_scenarios() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Get lab test scenarios from golden_labs.json.

    Returns:
        List of (scenario_id, scenario_dict) tuples for pytest parametrize
    """
    spec = load_golden_spec("golden_labs.json")
    scenarios = []

    for scenario in spec.get("lab_scenarios", []):
        scenario_id = scenario.get("scenario_id", "unknown")
        scenarios.append((scenario_id, scenario))

    return scenarios


def get_imaging_scenarios(modality: str = "ct") -> List[Tuple[str, Dict[str, Any]]]:
    """
    Get imaging test scenarios from golden spec files.

    Args:
        modality: "ct" or "mri"

    Returns:
        List of (scenario_id, scenario_dict) tuples
    """
    if modality == "ct":
        spec = load_golden_spec("golden_imaging_ct.json")
        key = "ct_scenarios"
    elif modality == "mri":
        spec = load_golden_spec("golden_imaging_mri.json")
        key = "mri_scenarios"
    else:
        raise ValueError(f"Unknown modality: {modality}")

    scenarios = []
    for scenario in spec.get(key, []):
        scenario_id = scenario.get("scenario_id", "unknown")
        scenarios.append((scenario_id, scenario))

    return scenarios


def get_caregap_scenarios() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Get care gap scenarios from golden_caregaps.json.

    Returns:
        List of (scenario_id, scenario_dict) tuples
    """
    spec = load_golden_spec("golden_caregaps.json")
    scenarios = []

    for scenario in spec.get("caregap_scenarios", []):
        scenario_id = scenario.get("scenario_id", "unknown")
        scenarios.append((scenario_id, scenario))

    return scenarios


def get_drug_interaction_scenarios() -> List[Tuple[str, Dict[str, Any]]]:
    """
    Get drug interaction scenarios from golden_drug_interactions.json.

    Returns:
        List of (scenario_id, scenario_dict) tuples
    """
    spec = load_golden_spec("golden_drug_interactions.json")
    scenarios = []

    for scenario in spec.get("interaction_scenarios", []):
        scenario_id = scenario.get("scenario_id", "unknown")
        scenarios.append((scenario_id, scenario))

    return scenarios


# =============================================================================
# Input builders - map golden spec fields to interpretation function params
# =============================================================================


def build_lab_input(scenario: Dict[str, Any]) -> Dict[str, str]:
    """
    Build input parameters for interpret_lab() from scenario.

    Maps golden spec fields to function parameters.
    """
    result_context = scenario.get("result_context", {})

    return {
        "test_name": scenario.get("test_name", ""),
        "meaning_category": result_context.get("meaning_category", "Normal"),
        "source_note": scenario.get("clinical_significance", ""),
    }


def build_imaging_input(scenario: Dict[str, Any]) -> Dict[str, str]:
    """
    Build input parameters for interpret_imaging_report() from scenario.

    Maps golden spec fields to function parameters.
    """
    report = scenario.get("radiology_report", {})
    report_text = f"FINDINGS: {report.get('findings', '')}\n\nIMPRESSION: {report.get('impression', '')}"

    return {
        "study_type": scenario.get("study_type", ""),
        "report_text": report_text,
        "flag": scenario.get("flag", "normal"),
    }


def build_caregap_input(scenario: Dict[str, Any]) -> Dict[str, str]:
    """
    Build input parameters for interpret_caregap() from scenario.

    Maps golden spec fields to function parameters.
    """
    return {
        "item_text": scenario.get("item_text", ""),
        "next_step": scenario.get("raw_next_step", ""),
        "time_bucket": scenario.get("time_bucket", "Later"),
    }


def build_medication_input(scenario: Dict[str, Any]) -> Dict[str, str]:
    """
    Build input parameters for interpret_medication() from scenario.

    Maps golden spec fields to function parameters.
    """
    drugs = scenario.get("drugs_involved", [])
    medication_name = drugs[0] if drugs else "Unknown"

    return {
        "medication_name": medication_name,
        "sig_text": "",  # Not in golden spec
        "clinician_notes": scenario.get("clinical_description", ""),
        "interaction_notes": scenario.get("what_happens", ""),
    }
