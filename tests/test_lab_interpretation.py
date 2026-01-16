"""
Tests for caremap.lab_interpretation module.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from caremap.lab_interpretation import interpret_lab, LAB_OUT_KEYS
from caremap.validators import ValidationError


class TestInterpretLab:
    """Tests for interpret_lab function."""

    def test_returns_dict_with_required_keys(self, mock_medgemma_client):
        """Test that output contains all required keys."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="Hemoglobin",
            meaning_category="Needs follow-up"
        )

        for key in LAB_OUT_KEYS:
            assert key in result

    def test_passes_test_name(self, mock_medgemma_client):
        """Test that test name is passed correctly."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="A1c",
            meaning_category="Normal"
        )

        mock_medgemma_client.generate.assert_called_once()
        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "A1c" in call_args

    def test_passes_meaning_category(self, mock_medgemma_client):
        """Test that meaning category is passed correctly."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="Cholesterol",
            meaning_category="Slightly off"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Slightly off" in call_args

    def test_handles_source_note(self, mock_medgemma_client):
        """Test that source note is passed."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="eGFR",
            meaning_category="Needs follow-up",
            source_note="Flagged low in portal"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Flagged low in portal" in call_args

    def test_handles_empty_source_note(self, mock_medgemma_client):
        """Test handling of empty source note."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="TSH",
            meaning_category="Normal",
            source_note=""
        )

        assert result is not None

    def test_strips_whitespace(self, mock_medgemma_client):
        """Test that input values are stripped."""
        result = interpret_lab(
            client=mock_medgemma_client,
            test_name="  Hemoglobin  ",
            meaning_category="  Normal  ",
            source_note="  Note  "
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Hemoglobin" in call_args

    def test_raises_on_invalid_json_response(self):
        """Test that ValidationError is raised on invalid JSON."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "Invalid JSON output"

        with pytest.raises(ValidationError):
            interpret_lab(
                client=mock_client,
                test_name="Test",
                meaning_category="Normal"
            )

    def test_raises_on_missing_keys(self):
        """Test that ValidationError is raised when keys are missing."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '{"what_was_checked": "Test"}'

        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            interpret_lab(
                client=mock_client,
                test_name="Test",
                meaning_category="Normal"
            )

    def test_raises_on_too_many_sentences_in_what_was_checked(self):
        """Test validation of sentence count in what_was_checked."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"what_was_checked": "First. Second.", "what_it_means": "Normal.", "what_to_ask_doctor": "Question?"}'''

        with pytest.raises(ValidationError, match="must be <= 1 sentence"):
            interpret_lab(
                client=mock_client,
                test_name="Test",
                meaning_category="Normal"
            )

    def test_raises_on_no_question_mark(self):
        """Test that exactly one question mark is required in what_to_ask_doctor."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"what_was_checked": "Blood test.", "what_it_means": "Normal result.", "what_to_ask_doctor": "No question here"}'''

        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            interpret_lab(
                client=mock_client,
                test_name="Test",
                meaning_category="Normal"
            )

    def test_raises_on_multiple_question_marks(self):
        """Test that multiple question marks are not allowed."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"what_was_checked": "Test.", "what_it_means": "Normal.", "what_to_ask_doctor": "Question one? Question two?"}'''

        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            interpret_lab(
                client=mock_client,
                test_name="Test",
                meaning_category="Normal"
            )


class TestLabOutKeys:
    """Tests for LAB_OUT_KEYS constant."""

    def test_contains_required_fields(self):
        """Test that all required output fields are defined."""
        assert "what_was_checked" in LAB_OUT_KEYS
        assert "what_it_means" in LAB_OUT_KEYS
        assert "what_to_ask_doctor" in LAB_OUT_KEYS

    def test_has_three_keys(self):
        """Test that exactly 3 keys are defined."""
        assert len(LAB_OUT_KEYS) == 3
