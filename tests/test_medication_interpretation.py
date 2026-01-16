"""
Tests for caremap.medication_interpretation module.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from caremap.medication_interpretation import interpret_medication, MED_OUT_KEYS
from caremap.validators import ValidationError


class TestInterpretMedication:
    """Tests for interpret_medication function."""

    def test_returns_dict_with_required_keys(self, mock_medgemma_client):
        """Test that output contains all required keys."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Metformin",
            when_to_give="Twice daily with meals"
        )

        for key in MED_OUT_KEYS:
            assert key in result

    def test_passes_medication_name(self, mock_medgemma_client):
        """Test that medication name is passed correctly."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Aspirin",
            when_to_give="Once daily"
        )

        # Verify generate was called
        mock_medgemma_client.generate.assert_called_once()
        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Aspirin" in call_args

    def test_handles_empty_when_to_give(self, mock_medgemma_client):
        """Test handling of empty timing."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Lisinopril",
            when_to_give=""
        )

        assert result is not None

    def test_handles_clinician_notes(self, mock_medgemma_client):
        """Test that clinician notes are passed."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Insulin",
            when_to_give="At bedtime",
            clinician_notes="Store in refrigerator"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Store in refrigerator" in call_args

    def test_handles_interaction_notes(self, mock_medgemma_client):
        """Test that interaction notes are passed."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Warfarin",
            when_to_give="Once daily",
            interaction_notes="Avoid with aspirin"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Avoid with aspirin" in call_args

    def test_strips_whitespace(self, mock_medgemma_client):
        """Test that input values are stripped of whitespace."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="  Metformin  ",
            when_to_give="  Morning  ",
            clinician_notes="  Note  ",
            interaction_notes="  Interaction  "
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        # Should contain stripped values
        assert "Metformin" in call_args

    def test_raises_on_invalid_json_response(self):
        """Test that ValidationError is raised on invalid JSON."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "Not valid JSON"

        with pytest.raises(ValidationError):
            interpret_medication(
                client=mock_client,
                medication_name="Test",
                when_to_give="Daily"
            )

    def test_raises_on_missing_keys(self):
        """Test that ValidationError is raised when keys are missing."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '{"medication": "Test"}'  # Missing other keys

        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            interpret_medication(
                client=mock_client,
                medication_name="Test",
                when_to_give="Daily"
            )

    def test_raises_on_too_many_sentences_in_why_it_matters(self):
        """Test that ValidationError is raised for multi-sentence why_it_matters."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"medication": "Test", "why_it_matters": "First sentence. Second sentence.", "when_to_give": "Daily", "important_note": ""}'''

        with pytest.raises(ValidationError, match="must be <= 1 sentence"):
            interpret_medication(
                client=mock_client,
                medication_name="Test",
                when_to_give="Daily"
            )

    def test_allows_empty_important_note(self, mock_medgemma_client):
        """Test that empty important_note is allowed."""
        result = interpret_medication(
            client=mock_medgemma_client,
            medication_name="Metformin",
            when_to_give="Daily"
        )

        # Should not raise - empty important_note is valid
        assert "important_note" in result


class TestMedOutKeys:
    """Tests for MED_OUT_KEYS constant."""

    def test_contains_required_fields(self):
        """Test that all required output fields are defined."""
        assert "medication" in MED_OUT_KEYS
        assert "why_it_matters" in MED_OUT_KEYS
        assert "when_to_give" in MED_OUT_KEYS
        assert "important_note" in MED_OUT_KEYS

    def test_has_four_keys(self):
        """Test that exactly 4 keys are defined."""
        assert len(MED_OUT_KEYS) == 4
