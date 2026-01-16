"""Integration tests for lab interpretation against golden specifications.

These tests validate that REAL MedGemma outputs:
1. Contain the correct structure (expected keys)
2. Do NOT contain forbidden terms (numbers, medical jargon)
3. Have non-empty meaningful values

Run tests:
    .venv/bin/python -m pytest tests/integration/test_golden_labs.py -v
"""
from __future__ import annotations

from typing import Any

import pytest

from caremap.lab_interpretation import LAB_OUT_KEYS, interpret_lab

from helpers.golden_validators import (
    assert_no_forbidden_terms,
    assert_non_empty_string_values,
    assert_output_keys_match,
    validate_golden_output,
)
from helpers.scenario_loader import (
    build_lab_input,
    extract_lab_scenarios,
    get_forbidden_terms,
    load_golden_spec,
)

# Load spec once at module level for parametrization
_GOLDEN_SPEC = load_golden_spec("golden_labs.json")
_LAB_SCENARIOS = extract_lab_scenarios(_GOLDEN_SPEC)


class TestGoldenLabs:
    """Real integration tests for lab interpretation with MedGemma."""

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _LAB_SCENARIOS,
        ids=[s[0] for s in _LAB_SCENARIOS],
    )
    def test_lab_output_structure(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that lab interpretation returns correct structure."""
        # Build input from scenario
        input_params = build_lab_input(scenario)

        # Call REAL interpretation function
        result = interpret_lab(
            client=medgemma_client,
            test_name=input_params["test_name"],
            meaning_category=input_params["meaning_category"],
            source_note=input_params["source_note"],
        )

        # Validate structure
        assert_output_keys_match(result, LAB_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _LAB_SCENARIOS,
        ids=[s[0] for s in _LAB_SCENARIOS],
    )
    def test_lab_non_empty_values(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that lab interpretation returns non-empty values."""
        input_params = build_lab_input(scenario)

        result = interpret_lab(
            client=medgemma_client,
            test_name=input_params["test_name"],
            meaning_category=input_params["meaning_category"],
            source_note=input_params["source_note"],
        )

        # Validate non-empty
        assert_non_empty_string_values(result, LAB_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _LAB_SCENARIOS,
        ids=[s[0] for s in _LAB_SCENARIOS],
    )
    def test_lab_no_forbidden_terms(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that lab interpretation excludes forbidden terms."""
        input_params = build_lab_input(scenario)

        result = interpret_lab(
            client=medgemma_client,
            test_name=input_params["test_name"],
            meaning_category=input_params["meaning_category"],
            source_note=input_params["source_note"],
        )

        # Get forbidden terms for this scenario
        forbidden = get_forbidden_terms(scenario)
        if forbidden:
            assert_no_forbidden_terms(result, forbidden, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _LAB_SCENARIOS,
        ids=[s[0] for s in _LAB_SCENARIOS],
    )
    def test_lab_comprehensive_validation(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Comprehensive validation of lab interpretation output."""
        input_params = build_lab_input(scenario)

        result = interpret_lab(
            client=medgemma_client,
            test_name=input_params["test_name"],
            meaning_category=input_params["meaning_category"],
            source_note=input_params["source_note"],
        )

        # Full validation
        forbidden = get_forbidden_terms(scenario)
        validate_golden_output(
            output=result,
            expected_keys=LAB_OUT_KEYS,
            forbidden_terms=forbidden,
            scenario_id=scenario_id,
            check_numerics=True,
        )
