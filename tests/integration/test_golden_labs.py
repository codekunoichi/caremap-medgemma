"""
Integration tests for lab interpretation against golden specifications.

Tests 8 lab scenarios from golden_labs.json using the real MedGemma model.

Run with:
    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_golden_labs.py -v
"""
from __future__ import annotations

import pytest

from caremap.lab_interpretation import interpret_lab, LAB_OUT_KEYS

from tests.helpers import (
    assert_no_forbidden_terms,
    assert_output_structure,
    assert_non_empty_values,
)
from tests.helpers.scenario_loader import get_lab_scenarios, build_lab_input


# Load scenarios for parametrization
_LAB_SCENARIOS = get_lab_scenarios()


@pytest.mark.parametrize("scenario_id,scenario", _LAB_SCENARIOS)
def test_lab_interpretation(medgemma_client, scenario_id, scenario):
    """
    Test real lab interpretation against golden spec.

    For each scenario:
    1. Call interpret_lab() with real MedGemma
    2. Validate output has correct structure
    3. Validate no forbidden terms appear
    4. Validate fields are non-empty
    """
    # Build input from scenario
    input_params = build_lab_input(scenario)

    # Call real interpretation function
    result = interpret_lab(
        client=medgemma_client,
        test_name=input_params["test_name"],
        meaning_category=input_params["meaning_category"],
        source_note=input_params["source_note"],
    )

    # Validate structure
    assert_output_structure(
        result,
        expected_keys=set(LAB_OUT_KEYS),
        scenario_id=scenario_id,
    )

    # Validate no forbidden terms
    forbidden = scenario.get("_forbidden_in_output", [])
    if forbidden:
        assert_no_forbidden_terms(result, forbidden, scenario_id)

    # Validate non-empty values
    assert_non_empty_values(result, scenario_id)


@pytest.mark.parametrize("scenario_id,scenario", _LAB_SCENARIOS)
def test_lab_no_numeric_leakage(medgemma_client, scenario_id, scenario):
    """
    Test that lab outputs don't leak specific numeric values.

    Lab results should never include:
    - Actual test values (e.g., "8.4%", "42 mL/min")
    - Reference ranges (e.g., "< 7.0%")
    """
    input_params = build_lab_input(scenario)

    result = interpret_lab(
        client=medgemma_client,
        test_name=input_params["test_name"],
        meaning_category=input_params["meaning_category"],
        source_note=input_params["source_note"],
    )

    # Check for numeric values in result context
    result_context = scenario.get("result_context", {})
    forbidden_numbers = []

    # Extract numeric values from the scenario
    if "value" in result_context:
        forbidden_numbers.append(result_context["value"])
    if "reference_range" in result_context:
        forbidden_numbers.append(result_context["reference_range"])

    # Also check any nested numeric fields
    for key, val in result_context.items():
        if isinstance(val, str) and any(c.isdigit() for c in val):
            forbidden_numbers.append(val)

    if forbidden_numbers:
        assert_no_forbidden_terms(result, forbidden_numbers, scenario_id)
