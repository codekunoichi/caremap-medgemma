"""Integration tests for drug interaction interpretation against golden specifications.

These tests validate that REAL MedGemma outputs:
1. Contain the correct structure (expected keys)
2. Have non-empty meaningful values
3. Provide practical guidance without medical jargon

Run tests:
    .venv/bin/python -m pytest tests/integration/test_golden_drug_interactions.py -v
"""
from __future__ import annotations

from typing import Any

import pytest

from caremap.medication_interpretation import MED_OUT_KEYS, interpret_medication

from helpers.golden_validators import (
    assert_no_forbidden_terms,
    assert_non_empty_string_values,
    assert_output_keys_match,
)
from helpers.scenario_loader import (
    build_interaction_input,
    extract_interaction_scenarios,
    load_golden_spec,
)

# Load spec once at module level for parametrization
_GOLDEN_SPEC = load_golden_spec("golden_drug_interactions.json")
_INTERACTION_SCENARIOS = extract_interaction_scenarios(_GOLDEN_SPEC)

# General forbidden terms for drug interactions (from spec's _medgemma_instructions)
INTERACTION_FORBIDDEN_TERMS = [
    "mg/dL",
    "mEq/L",
    "INR",
    "GI",
    "GFR",
    "CNS",
    "NSAID",  # Should explain as "pain relievers like ibuprofen"
]


class TestGoldenDrugInteractions:
    """Real integration tests for drug interaction interpretation with MedGemma."""

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _INTERACTION_SCENARIOS,
        ids=[s[0] for s in _INTERACTION_SCENARIOS],
    )
    def test_interaction_output_structure(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that drug interaction interpretation returns correct structure."""
        input_params = build_interaction_input(scenario)

        result = interpret_medication(
            client=medgemma_client,
            medication_name=input_params["medication_name"],
            when_to_give=input_params["when_to_give"],
            clinician_notes=input_params["clinician_notes"],
            interaction_notes=input_params["interaction_notes"],
        )

        # Validate structure
        assert_output_keys_match(result, MED_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _INTERACTION_SCENARIOS,
        ids=[s[0] for s in _INTERACTION_SCENARIOS],
    )
    def test_interaction_non_empty_values(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that drug interaction interpretation returns non-empty values."""
        input_params = build_interaction_input(scenario)

        result = interpret_medication(
            client=medgemma_client,
            medication_name=input_params["medication_name"],
            when_to_give=input_params["when_to_give"],
            clinician_notes=input_params["clinician_notes"],
            interaction_notes=input_params["interaction_notes"],
        )

        # Validate non-empty for key fields
        # Note: when_to_give may be empty for interaction scenarios
        required_non_empty = ["medication", "why_it_matters"]
        assert_non_empty_string_values(result, required_non_empty, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _INTERACTION_SCENARIOS,
        ids=[s[0] for s in _INTERACTION_SCENARIOS],
    )
    def test_interaction_no_medical_abbreviations(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that drug interaction interpretation avoids unexplained medical abbreviations."""
        input_params = build_interaction_input(scenario)

        result = interpret_medication(
            client=medgemma_client,
            medication_name=input_params["medication_name"],
            when_to_give=input_params["when_to_give"],
            clinician_notes=input_params["clinician_notes"],
            interaction_notes=input_params["interaction_notes"],
        )

        # Check general forbidden terms
        assert_no_forbidden_terms(result, INTERACTION_FORBIDDEN_TERMS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _INTERACTION_SCENARIOS,
        ids=[s[0] for s in _INTERACTION_SCENARIOS],
    )
    def test_interaction_medication_name_preserved(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that medication name is preserved in output."""
        input_params = build_interaction_input(scenario)

        result = interpret_medication(
            client=medgemma_client,
            medication_name=input_params["medication_name"],
            when_to_give=input_params["when_to_give"],
            clinician_notes=input_params["clinician_notes"],
            interaction_notes=input_params["interaction_notes"],
        )

        # The medication field should contain the medication name
        assert result.get("medication"), f"[{scenario_id}] medication field is empty"
        # Medication name should appear somewhere in the result
        medication_lower = input_params["medication_name"].lower()
        result_medication_lower = result.get("medication", "").lower()
        assert medication_lower in result_medication_lower, (
            f"[{scenario_id}] Expected '{input_params['medication_name']}' "
            f"in output medication field, got '{result.get('medication')}'"
        )
