"""Integration tests for MRI imaging interpretation against golden specifications.

These tests validate that REAL MedGemma outputs:
1. Contain the correct structure (expected keys)
2. Do NOT contain forbidden terms (radiology jargon)
3. Have non-empty meaningful values

Run tests:
    .venv/bin/python -m pytest tests/integration/test_golden_imaging_mri.py -v
"""
from __future__ import annotations

from typing import Any

import pytest

from caremap.imaging_interpretation import IMAGING_OUT_KEYS, interpret_imaging_report

from helpers.golden_validators import (
    assert_no_forbidden_terms,
    assert_non_empty_string_values,
    assert_output_keys_match,
    validate_golden_output,
)
from helpers.scenario_loader import (
    build_imaging_input,
    extract_mri_scenarios,
    get_forbidden_terms,
    load_golden_spec,
)

# Load spec once at module level for parametrization
_GOLDEN_SPEC = load_golden_spec("golden_imaging_mri.json")
_MRI_SCENARIOS = extract_mri_scenarios(_GOLDEN_SPEC)


class TestGoldenImagingMRI:
    """Real integration tests for MRI imaging interpretation with MedGemma."""

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _MRI_SCENARIOS,
        ids=[s[0] for s in _MRI_SCENARIOS],
    )
    def test_mri_output_structure(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that MRI interpretation returns correct structure."""
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Validate structure
        assert_output_keys_match(result, IMAGING_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _MRI_SCENARIOS,
        ids=[s[0] for s in _MRI_SCENARIOS],
    )
    def test_mri_non_empty_values(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that MRI interpretation returns non-empty values."""
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Validate non-empty
        assert_non_empty_string_values(result, IMAGING_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _MRI_SCENARIOS,
        ids=[s[0] for s in _MRI_SCENARIOS],
    )
    def test_mri_no_forbidden_terms(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that MRI interpretation excludes forbidden radiology terms."""
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Get forbidden terms for this scenario
        forbidden = get_forbidden_terms(scenario)
        if forbidden:
            assert_no_forbidden_terms(result, forbidden, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _MRI_SCENARIOS,
        ids=[s[0] for s in _MRI_SCENARIOS],
    )
    def test_mri_comprehensive_validation(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Comprehensive validation of MRI interpretation output."""
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Full validation
        forbidden = get_forbidden_terms(scenario)
        validate_golden_output(
            output=result,
            expected_keys=IMAGING_OUT_KEYS,
            forbidden_terms=forbidden,
            scenario_id=scenario_id,
            check_numerics=True,
        )
