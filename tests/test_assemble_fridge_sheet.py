"""
Tests for caremap.assemble_fridge_sheet module.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from caremap.assemble_fridge_sheet import (
    BuildLimits,
    _extract_when_to_give,
    build_fridge_sheet,
)


class TestBuildLimits:
    """Tests for BuildLimits dataclass."""

    def test_default_values(self):
        """Test default limit values."""
        limits = BuildLimits()
        assert limits.max_meds == 8
        assert limits.max_labs == 3
        assert limits.max_actions_today == 2
        assert limits.max_actions_week == 2
        assert limits.max_actions_later == 1

    def test_custom_values(self):
        """Test custom limit values."""
        limits = BuildLimits(
            max_meds=5,
            max_labs=2,
            max_actions_today=1,
            max_actions_week=1,
            max_actions_later=0
        )
        assert limits.max_meds == 5
        assert limits.max_labs == 2
        assert limits.max_actions_today == 1
        assert limits.max_actions_week == 1
        assert limits.max_actions_later == 0


class TestExtractWhenToGive:
    """Tests for _extract_when_to_give helper function."""

    def test_prefers_timing_field(self):
        """Test that timing field is preferred over sig_text."""
        med = {
            "timing": "morning and evening",
            "sig_text": "Take 1 tablet twice daily"
        }
        result = _extract_when_to_give(med)
        assert result == "morning and evening"

    def test_falls_back_to_sig_text(self):
        """Test fallback to sig_text when timing is empty."""
        med = {
            "timing": "",
            "sig_text": "Take 1 tablet twice daily"
        }
        result = _extract_when_to_give(med)
        assert result == "Take 1 tablet twice daily"

    def test_returns_empty_when_both_missing(self):
        """Test returns empty string when both fields missing."""
        med = {"timing": "", "sig_text": ""}
        result = _extract_when_to_give(med)
        assert result == ""

    def test_handles_missing_fields(self):
        """Test handles completely missing fields."""
        med = {}
        result = _extract_when_to_give(med)
        assert result == ""

    def test_strips_whitespace(self):
        """Test that whitespace is stripped."""
        med = {"timing": "  morning  ", "sig_text": ""}
        result = _extract_when_to_give(med)
        assert result == "morning"

    def test_timing_whitespace_only_falls_back(self):
        """Test that whitespace-only timing falls back to sig_text."""
        med = {"timing": "   ", "sig_text": "Once daily"}
        result = _extract_when_to_give(med)
        assert result == "Once daily"


class TestBuildFridgeSheet:
    """Tests for build_fridge_sheet function."""

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_returns_complete_structure(
        self, mock_caregap, mock_lab, mock_med, sample_canonical_patient_v11
    ):
        """Test that output has all required sections."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        mock_client = MagicMock()
        result = build_fridge_sheet(sample_canonical_patient_v11, mock_client)

        assert "meta" in result
        assert "patient" in result
        assert "medications" in result
        assert "labs" in result
        assert "actions" in result
        assert "contacts" in result

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_meta_section(self, mock_caregap, mock_lab, mock_med, sample_canonical_patient_v11):
        """Test meta section is populated correctly."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        mock_client = MagicMock()
        result = build_fridge_sheet(sample_canonical_patient_v11, mock_client)

        assert result["meta"]["generated_on"] == "2026-01-15"
        assert result["meta"]["language"] == "en"
        assert result["meta"]["source"] == "CCDA"

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_patient_section(self, mock_caregap, mock_lab, mock_med, sample_canonical_patient_v11):
        """Test patient section is populated correctly."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        mock_client = MagicMock()
        result = build_fridge_sheet(sample_canonical_patient_v11, mock_client)

        assert result["patient"]["nickname"] == "TestPatient"
        assert result["patient"]["age_range"] == "60s"
        assert len(result["patient"]["conditions"]) <= 3

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_limits_conditions_to_three(self, mock_caregap, mock_lab, mock_med):
        """Test that conditions are limited to 3."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "patient": {
                "conditions_display": ["A", "B", "C", "D", "E"]
            }
        }
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        assert len(result["patient"]["conditions"]) == 3

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_respects_max_meds_limit(self, mock_caregap, mock_lab, mock_med):
        """Test that medications are limited by max_meds."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "medications": [{"medication_name": f"Med{i}"} for i in range(15)]
        }
        mock_client = MagicMock()
        limits = BuildLimits(max_meds=5)
        result = build_fridge_sheet(patient, mock_client, limits=limits)

        assert len(result["medications"]) == 5
        assert mock_med.call_count == 5

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_respects_max_labs_limit(self, mock_caregap, mock_lab, mock_med):
        """Test that labs are limited by max_labs."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "results": [{"test_name": f"Lab{i}", "meaning_category": "Normal"} for i in range(10)]
        }
        mock_client = MagicMock()
        limits = BuildLimits(max_labs=2)
        result = build_fridge_sheet(patient, mock_client, limits=limits)

        assert len(result["labs"]) == 2
        assert mock_lab.call_count == 2

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_respects_action_bucket_limits(self, mock_caregap, mock_lab, mock_med):
        """Test that action buckets respect their limits."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "care_gaps": [
                {"item_text": "Task1", "next_step": "Do", "time_bucket": "Today"},
                {"item_text": "Task2", "next_step": "Do", "time_bucket": "Today"},
                {"item_text": "Task3", "next_step": "Do", "time_bucket": "Today"},
                {"item_text": "Task4", "next_step": "Do", "time_bucket": "This Week"},
                {"item_text": "Task5", "next_step": "Do", "time_bucket": "This Week"},
                {"item_text": "Task6", "next_step": "Do", "time_bucket": "This Week"},
                {"item_text": "Task7", "next_step": "Do", "time_bucket": "Later"},
                {"item_text": "Task8", "next_step": "Do", "time_bucket": "Later"},
            ]
        }
        mock_client = MagicMock()
        limits = BuildLimits(max_actions_today=2, max_actions_week=2, max_actions_later=1)
        result = build_fridge_sheet(patient, mock_client, limits=limits)

        assert len(result["actions"]["Today"]) <= 2
        assert len(result["actions"]["This Week"]) <= 2
        assert len(result["actions"]["Later"]) <= 1

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_ignores_unknown_time_buckets(self, mock_caregap, mock_lab, mock_med):
        """Test that unknown time buckets are ignored."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "care_gaps": [
                {"item_text": "Task1", "next_step": "Do", "time_bucket": "Unknown"},
                {"item_text": "Task2", "next_step": "Do", "time_bucket": "Invalid"},
            ]
        }
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        # Should not call interpret_caregap for unknown buckets
        assert mock_caregap.call_count == 0

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_contacts_section(self, mock_caregap, mock_lab, mock_med, sample_canonical_patient_v11):
        """Test contacts section is populated correctly."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        mock_client = MagicMock()
        result = build_fridge_sheet(sample_canonical_patient_v11, mock_client)

        assert result["contacts"]["clinic"]["name"] == "Test Clinic"
        assert result["contacts"]["clinic"]["phone"] == "555-1234"
        assert result["contacts"]["pharmacy"]["name"] == "Test Pharmacy"
        assert result["contacts"]["pharmacy"]["phone"] == "555-5678"

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_missing_contacts_show_not_available(self, mock_caregap, mock_lab, mock_med):
        """Test that missing contacts show 'Not available'."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {"contacts": {}}
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        assert result["contacts"]["clinic"]["name"] == "Not available"
        assert result["contacts"]["clinic"]["phone"] == "Not available"
        assert result["contacts"]["pharmacy"]["name"] == "Not available"
        assert result["contacts"]["pharmacy"]["phone"] == "Not available"

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_handles_minimal_patient(self, mock_caregap, mock_lab, mock_med, minimal_canonical_patient):
        """Test handling of minimal patient data."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        mock_client = MagicMock()
        result = build_fridge_sheet(minimal_canonical_patient, mock_client)

        assert result is not None
        assert len(result["medications"]) == 1
        assert len(result["labs"]) == 0
        assert len(result["actions"]["Today"]) == 0

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_uses_current_date_when_not_provided(self, mock_caregap, mock_lab, mock_med):
        """Test that current date is used when meta.generated_on is missing."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {}  # No meta section
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        assert result["meta"]["generated_on"] == date.today().isoformat()

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_default_language_is_english(self, mock_caregap, mock_lab, mock_med):
        """Test that default language is English."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {}
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        assert result["meta"]["language"] == "en"

    @patch("caremap.assemble_fridge_sheet.interpret_medication")
    @patch("caremap.assemble_fridge_sheet.interpret_lab")
    @patch("caremap.assemble_fridge_sheet.interpret_caregap")
    def test_extracts_timing_correctly(self, mock_caregap, mock_lab, mock_med):
        """Test that timing is extracted from medication correctly."""
        mock_med.return_value = {"medication": "Test", "why_it_matters": "", "when_to_give": "", "important_note": ""}
        mock_lab.return_value = {"what_was_checked": "", "what_it_means": "", "what_to_ask_doctor": "?"}
        mock_caregap.return_value = {"time_bucket": "Today", "action_item": "", "next_step": ""}

        patient = {
            "medications": [
                {"medication_name": "Med1", "timing": "morning", "sig_text": "Take once daily"}
            ]
        }
        mock_client = MagicMock()
        result = build_fridge_sheet(patient, mock_client)

        # Check that interpret_medication was called with timing (morning)
        call_args = mock_med.call_args
        assert call_args[1]["when_to_give"] == "morning"
