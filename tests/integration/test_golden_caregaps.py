"""
Integration tests for care gap interpretation against golden specifications.

Tests 10 care gap scenarios from golden_caregaps.json using real MedGemma.

Run with:
    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_golden_caregaps.py -v
"""
from __future__ import annotations

import pytest

from caremap.caregap_interpretation import interpret_caregap, CARE_OUT_KEYS

from tests.helpers import (
    assert_no_forbidden_terms,
    assert_output_structure,
    assert_non_empty_values,
)
from tests.helpers.scenario_loader import get_caregap_scenarios, build_caregap_input


# Load scenarios for parametrization
_CAREGAP_SCENARIOS = get_caregap_scenarios()


@pytest.mark.parametrize("scenario_id,scenario", _CAREGAP_SCENARIOS)
def test_caregap_interpretation(medgemma_client, scenario_id, scenario):
    """
    Test care gap interpretation against golden spec.
    """
    input_params = build_caregap_input(scenario)

    result = interpret_caregap(
        client=medgemma_client,
        item_text=input_params["item_text"],
        next_step=input_params["next_step"],
        time_bucket=input_params["time_bucket"],
    )

    # Validate structure
    assert_output_structure(
        result,
        expected_keys=set(CARE_OUT_KEYS),
        scenario_id=scenario_id,
    )

    # Validate non-empty values
    assert_non_empty_values(result, scenario_id)


@pytest.mark.parametrize("scenario_id,scenario", _CAREGAP_SCENARIOS)
def test_caregap_time_bucket_preserved(medgemma_client, scenario_id, scenario):
    """
    Test that time_bucket from input is preserved in output.
    """
    input_params = build_caregap_input(scenario)
    expected_bucket = input_params["time_bucket"]

    result = interpret_caregap(
        client=medgemma_client,
        item_text=input_params["item_text"],
        next_step=input_params["next_step"],
        time_bucket=input_params["time_bucket"],
    )

    assert result["time_bucket"] == expected_bucket, (
        f"[{scenario_id}] Expected time_bucket '{expected_bucket}', "
        f"got '{result['time_bucket']}'"
    )


@pytest.mark.parametrize("scenario_id,scenario", _CAREGAP_SCENARIOS)
def test_caregap_no_medical_abbreviations(medgemma_client, scenario_id, scenario):
    """
    Test that care gap outputs don't contain unexplained medical abbreviations.
    """
    input_params = build_caregap_input(scenario)

    result = interpret_caregap(
        client=medgemma_client,
        item_text=input_params["item_text"],
        next_step=input_params["next_step"],
        time_bucket=input_params["time_bucket"],
    )

    # Common abbreviations that should be explained or avoided
    abbreviations = [
        "PHQ-9", "eGFR", "A1c", "HbA1c", "INR", "PT", "BNP",
        "CKD", "CHF", "AFib", "CAD", "COPD", "DM",
        "NPO", "PRN", "BID", "TID", "QID",
    ]

    # Check for abbreviations (case-sensitive for these)
    all_text = " ".join(str(v) for v in result.values() if isinstance(v, str))

    found_abbrev = []
    for abbrev in abbreviations:
        if abbrev in all_text:
            found_abbrev.append(abbrev)

    assert not found_abbrev, (
        f"[{scenario_id}] Found unexplained abbreviations: {found_abbrev}"
    )
