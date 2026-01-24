"""
Integration tests for medication/drug interaction interpretation.

Tests drug interaction scenarios from golden_drug_interactions.json.

Run with:
    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_golden_medications.py -v
"""
from __future__ import annotations

import pytest

from caremap.medication_interpretation import (
    interpret_medication_v3_grounded,
    MED_V3_OUT_KEYS,
)

from tests.helpers import (
    assert_no_forbidden_terms,
    assert_output_structure,
    assert_non_empty_values,
)
from tests.helpers.scenario_loader import (
    get_drug_interaction_scenarios,
    build_medication_input,
)


# Load scenarios for parametrization
_INTERACTION_SCENARIOS = get_drug_interaction_scenarios()


@pytest.mark.parametrize("scenario_id,scenario", _INTERACTION_SCENARIOS)
def test_medication_interpretation(medgemma_client, scenario_id, scenario):
    """
    Test medication/interaction interpretation against golden spec.
    """
    input_params = build_medication_input(scenario)

    result, raw = interpret_medication_v3_grounded(
        client=medgemma_client,
        medication_name=input_params["medication_name"],
        sig_text=input_params["sig_text"],
        clinician_notes=input_params["clinician_notes"],
        interaction_notes=input_params["interaction_notes"],
    )

    # Check for parse errors
    assert "raw_response" not in result, (
        f"[{scenario_id}] JSON parsing failed: {raw[:200]}"
    )

    # Validate structure
    assert_output_structure(
        result,
        expected_keys=set(MED_V3_OUT_KEYS),
        scenario_id=scenario_id,
    )

    # Validate non-empty values
    assert_non_empty_values(result, scenario_id)


@pytest.mark.parametrize("scenario_id,scenario", _INTERACTION_SCENARIOS)
def test_medication_preserves_name(medgemma_client, scenario_id, scenario):
    """
    Test that medication name is preserved in output.
    """
    input_params = build_medication_input(scenario)
    expected_name = input_params["medication_name"]

    result, _ = interpret_medication_v3_grounded(
        client=medgemma_client,
        medication_name=input_params["medication_name"],
        sig_text=input_params["sig_text"],
        clinician_notes=input_params["clinician_notes"],
        interaction_notes=input_params["interaction_notes"],
    )

    if "raw_response" in result:
        pytest.skip("JSON parsing failed")

    assert result["medication"] == expected_name, (
        f"[{scenario_id}] Medication name not preserved: "
        f"expected '{expected_name}', got '{result['medication']}'"
    )


@pytest.mark.parametrize("scenario_id,scenario", _INTERACTION_SCENARIOS)
def test_medication_captures_safety_info(medgemma_client, scenario_id, scenario):
    """
    Test that key safety information is captured in output.
    """
    input_params = build_medication_input(scenario)

    result, _ = interpret_medication_v3_grounded(
        client=medgemma_client,
        medication_name=input_params["medication_name"],
        sig_text=input_params["sig_text"],
        clinician_notes=input_params["clinician_notes"],
        interaction_notes=input_params["interaction_notes"],
    )

    if "raw_response" in result:
        pytest.skip("JSON parsing failed")

    # Check that watch_out_for is substantive
    watch_out = result.get("watch_out_for", "")
    assert len(watch_out) > 50, (
        f"[{scenario_id}] watch_out_for too short ({len(watch_out)} chars): "
        f"'{watch_out[:100]}...'"
    )

    # Check that it mentions something relevant from the interaction notes
    interaction_text = scenario.get("what_happens", "").lower()
    output_text = watch_out.lower()

    # At least some keywords should appear
    keywords = [w for w in interaction_text.split() if len(w) > 4][:5]
    found_any = any(kw in output_text for kw in keywords)

    assert found_any or len(keywords) == 0, (
        f"[{scenario_id}] watch_out_for doesn't seem to address the interaction. "
        f"Expected keywords from: '{interaction_text[:100]}...'"
    )
