"""Scenario loader for golden specification tests.

Loads golden specification files and extracts scenarios for pytest parametrization.
Also provides input builders to map scenario fields to interpretation function parameters.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_SPECS_DIR = Path(__file__).parent.parent.parent / "examples"


def load_golden_spec(spec_name: str) -> dict[str, Any]:
    """Load a golden specification file by name.

    Args:
        spec_name: Filename (e.g., "golden_labs.json")

    Returns:
        Parsed JSON specification
    """
    spec_path = GOLDEN_SPECS_DIR / spec_name
    with open(spec_path) as f:
        return json.load(f)


def extract_lab_scenarios(
    spec: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract lab scenarios from specification for pytest.mark.parametrize.

    Returns:
        List of (scenario_id, scenario_data) tuples
    """
    scenarios = spec.get("lab_scenarios", [])
    return [(s["scenario_id"], s) for s in scenarios]


def extract_ct_scenarios(
    spec: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract CT imaging scenarios from specification."""
    scenarios = spec.get("ct_scenarios", [])
    return [(s["scenario_id"], s) for s in scenarios]


def extract_mri_scenarios(
    spec: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract MRI imaging scenarios from specification."""
    scenarios = spec.get("mri_scenarios", [])
    return [(s["scenario_id"], s) for s in scenarios]


def extract_caregap_scenarios(
    spec: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract care gap scenarios from specification."""
    scenarios = spec.get("caregap_scenarios", [])
    return [(s["scenario_id"], s) for s in scenarios]


def extract_interaction_scenarios(
    spec: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    """Extract drug interaction scenarios from specification."""
    scenarios = spec.get("interaction_scenarios", [])
    return [(s["scenario_id"], s) for s in scenarios]


def build_lab_input(scenario: dict[str, Any]) -> dict[str, str]:
    """Build input parameters for interpret_lab from a lab scenario.

    Maps golden spec fields to function parameters:
    - test_name: from scenario["test_name"]
    - meaning_category: from scenario["result_context"]["meaning_category"]
    - source_note: from scenario["clinical_significance"] or flag description
    """
    result_context = scenario.get("result_context", {})
    return {
        "test_name": scenario.get("test_name", ""),
        "meaning_category": result_context.get("meaning_category", "Normal"),
        "source_note": scenario.get("clinical_significance", ""),
    }


def build_imaging_input(scenario: dict[str, Any]) -> dict[str, str]:
    """Build input parameters for interpret_imaging_report from an imaging scenario.

    Maps golden spec fields:
    - study_type: from scenario["study_type"]
    - report_text: combined findings + impression
    - flag: from scenario["flag"]
    """
    report = scenario.get("radiology_report", {})
    findings = report.get("findings", "")
    impression = report.get("impression", "")
    report_text = f"Findings: {findings}\n\nImpression: {impression}"

    return {
        "study_type": scenario.get("study_type", ""),
        "report_text": report_text,
        "flag": scenario.get("flag", "normal"),
    }


def build_caregap_input(scenario: dict[str, Any]) -> dict[str, str]:
    """Build input parameters for interpret_caregap from a caregap scenario.

    Maps golden spec fields:
    - item_text: from scenario["item_text"]
    - next_step: from scenario["raw_next_step"]
    - time_bucket: from scenario["time_bucket"]
    """
    return {
        "item_text": scenario.get("item_text", ""),
        "next_step": scenario.get("raw_next_step", ""),
        "time_bucket": scenario.get("time_bucket", "This Week"),
    }


def build_interaction_input(scenario: dict[str, Any]) -> dict[str, str]:
    """Build input parameters for interpret_medication from a drug interaction scenario.

    Maps interaction scenario fields to medication interpretation:
    - medication_name: from scenario["drugs_involved"][0]
    - when_to_give: empty (not specified in interaction scenarios)
    - clinician_notes: from scenario["what_happens"]
    - interaction_notes: from scenario["clinical_description"]
    """
    drugs = scenario.get("drugs_involved", [])
    medication_name = drugs[0] if drugs else ""

    return {
        "medication_name": medication_name,
        "when_to_give": "",
        "clinician_notes": scenario.get("what_happens", ""),
        "interaction_notes": scenario.get("clinical_description", ""),
    }


def get_forbidden_terms(scenario: dict[str, Any]) -> list[str]:
    """Extract forbidden terms from a scenario.

    Looks for '_forbidden_in_output' field which lists terms that
    should NOT appear in MedGemma's output.
    """
    return scenario.get("_forbidden_in_output", [])
