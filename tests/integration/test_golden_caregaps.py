"""Integration tests for care gap interpretation against golden specifications.

These tests validate that REAL MedGemma outputs:
1. Contain the correct structure (expected keys)
2. Have valid time bucket values (Today, This Week, Later)
3. Have non-empty meaningful values

Run tests:
    .venv/bin/python -m pytest tests/integration/test_golden_caregaps.py -v
"""
from __future__ import annotations

from typing import Any

import pytest

from caremap.caregap_interpretation import CARE_OUT_KEYS, interpret_caregap

from helpers.golden_validators import (
    assert_no_forbidden_terms,
    assert_non_empty_string_values,
    assert_output_keys_match,
)
from helpers.scenario_loader import (
    build_caregap_input,
    extract_caregap_scenarios,
    load_golden_spec,
)

# Load spec once at module level for parametrization
_GOLDEN_SPEC = load_golden_spec("golden_caregaps.json")
_CAREGAP_SCENARIOS = extract_caregap_scenarios(_GOLDEN_SPEC)

# Valid time bucket values
VALID_TIME_BUCKETS = {"Today", "This Week", "Later"}

# General forbidden terms for care gaps (medical abbreviations)
CAREGAP_FORBIDDEN_TERMS = [
    "PHQ-9",
    "eGFR",
    "HbA1c",
    "A1c",
    "PCV20",
    "PPSV23",
    "LI-RADS",
    "INR",
    "BNP",
]


class TestGoldenCaregaps:
    """Real integration tests for care gap interpretation with MedGemma."""

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _CAREGAP_SCENARIOS,
        ids=[s[0] for s in _CAREGAP_SCENARIOS],
    )
    def test_caregap_output_structure(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that care gap interpretation returns correct structure."""
        input_params = build_caregap_input(scenario)

        result = interpret_caregap(
            client=medgemma_client,
            item_text=input_params["item_text"],
            next_step=input_params["next_step"],
            time_bucket=input_params["time_bucket"],
        )

        # Validate structure
        assert_output_keys_match(result, CARE_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _CAREGAP_SCENARIOS,
        ids=[s[0] for s in _CAREGAP_SCENARIOS],
    )
    def test_caregap_non_empty_values(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that care gap interpretation returns non-empty values."""
        input_params = build_caregap_input(scenario)

        result = interpret_caregap(
            client=medgemma_client,
            item_text=input_params["item_text"],
            next_step=input_params["next_step"],
            time_bucket=input_params["time_bucket"],
        )

        # Validate non-empty
        assert_non_empty_string_values(result, CARE_OUT_KEYS, scenario_id)

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _CAREGAP_SCENARIOS,
        ids=[s[0] for s in _CAREGAP_SCENARIOS],
    )
    def test_caregap_valid_time_bucket(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that time bucket is a valid value."""
        input_params = build_caregap_input(scenario)

        result = interpret_caregap(
            client=medgemma_client,
            item_text=input_params["item_text"],
            next_step=input_params["next_step"],
            time_bucket=input_params["time_bucket"],
        )

        assert result.get("time_bucket") in VALID_TIME_BUCKETS, (
            f"[{scenario_id}] Invalid time_bucket: {result.get('time_bucket')}"
        )

    @pytest.mark.parametrize(
        "scenario_id,scenario",
        _CAREGAP_SCENARIOS,
        ids=[s[0] for s in _CAREGAP_SCENARIOS],
    )
    def test_caregap_no_medical_abbreviations(
        self,
        medgemma_client,
        scenario_id: str,
        scenario: dict[str, Any],
    ):
        """Test that care gap interpretation excludes medical abbreviations."""
        input_params = build_caregap_input(scenario)

        result = interpret_caregap(
            client=medgemma_client,
            item_text=input_params["item_text"],
            next_step=input_params["next_step"],
            time_bucket=input_params["time_bucket"],
        )

        # Check general forbidden terms
        assert_no_forbidden_terms(result, CAREGAP_FORBIDDEN_TERMS, scenario_id)
