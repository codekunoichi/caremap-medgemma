"""
Integration tests for imaging interpretation against golden specifications.

Tests CT and MRI scenarios using the real MedGemma model.

Run with:
    PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_golden_imaging.py -v
"""
from __future__ import annotations

import pytest

from caremap.imaging_interpretation import interpret_imaging_report, IMAGING_OUT_KEYS

from tests.helpers import (
    assert_no_forbidden_terms,
    assert_output_structure,
    assert_non_empty_values,
)
from tests.helpers.scenario_loader import get_imaging_scenarios, build_imaging_input


# Load scenarios for parametrization
_CT_SCENARIOS = get_imaging_scenarios("ct")
_MRI_SCENARIOS = get_imaging_scenarios("mri")


class TestCTImaging:
    """Tests for CT scan interpretation."""

    @pytest.mark.parametrize("scenario_id,scenario", _CT_SCENARIOS)
    def test_ct_interpretation(self, medgemma_client, scenario_id, scenario):
        """
        Test CT interpretation against golden spec.
        """
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Validate structure
        assert_output_structure(
            result,
            expected_keys=set(IMAGING_OUT_KEYS),
            scenario_id=scenario_id,
        )

        # Validate no forbidden terms
        forbidden = scenario.get("_forbidden_in_output", [])
        if forbidden:
            assert_no_forbidden_terms(result, forbidden, scenario_id)

        # Validate non-empty values
        assert_non_empty_values(result, scenario_id)

    @pytest.mark.parametrize("scenario_id,scenario", _CT_SCENARIOS)
    def test_ct_no_radiology_jargon(self, medgemma_client, scenario_id, scenario):
        """
        Test that CT outputs don't contain radiology jargon.
        """
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Common radiology jargon that should never appear
        radiology_jargon = [
            "opacities", "consolidation", "atelectasis", "effusion",
            "nodule", "lesion", "mass", "adenopathy", "lymphadenopathy",
            "hepatomegaly", "splenomegaly", "cardiomegaly",
            "stenosis", "occlusion", "aneurysm",
        ]

        # Only check terms not already in forbidden list
        forbidden = scenario.get("_forbidden_in_output", [])
        additional_jargon = [j for j in radiology_jargon if j not in forbidden]

        if additional_jargon:
            assert_no_forbidden_terms(result, additional_jargon, scenario_id)


class TestMRIImaging:
    """Tests for MRI scan interpretation."""

    @pytest.mark.parametrize("scenario_id,scenario", _MRI_SCENARIOS)
    def test_mri_interpretation(self, medgemma_client, scenario_id, scenario):
        """
        Test MRI interpretation against golden spec.
        """
        input_params = build_imaging_input(scenario)

        result = interpret_imaging_report(
            client=medgemma_client,
            study_type=input_params["study_type"],
            report_text=input_params["report_text"],
            flag=input_params["flag"],
        )

        # Validate structure
        assert_output_structure(
            result,
            expected_keys=set(IMAGING_OUT_KEYS),
            scenario_id=scenario_id,
        )

        # Validate no forbidden terms
        forbidden = scenario.get("_forbidden_in_output", [])
        if forbidden:
            assert_no_forbidden_terms(result, forbidden, scenario_id)

        # Validate non-empty values
        assert_non_empty_values(result, scenario_id)
