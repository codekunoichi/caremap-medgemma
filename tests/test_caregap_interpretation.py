"""
Tests for caremap.caregap_interpretation module.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from caremap.caregap_interpretation import interpret_caregap, CARE_OUT_KEYS
from caremap.validators import ValidationError


class TestInterpretCaregap:
    """Tests for interpret_caregap function."""

    def test_returns_dict_with_required_keys(self, mock_medgemma_client):
        """Test that output contains all required keys."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Eye exam overdue",
            next_step="Call clinic",
            time_bucket="This Week"
        )

        for key in CARE_OUT_KEYS:
            assert key in result

    def test_passes_item_text(self, mock_medgemma_client):
        """Test that item text is passed correctly."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Blood work due",
            next_step="Schedule lab",
            time_bucket="Today"
        )

        mock_medgemma_client.generate.assert_called_once()
        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Blood work due" in call_args

    def test_passes_next_step(self, mock_medgemma_client):
        """Test that next step is passed correctly."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Flu shot recommended",
            next_step="Ask pharmacy",
            time_bucket="Later"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Ask pharmacy" in call_args

    def test_passes_time_bucket(self, mock_medgemma_client):
        """Test that time bucket is passed correctly."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Follow-up visit",
            next_step="Call clinic",
            time_bucket="This Week"
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "This Week" in call_args

    def test_handles_today_bucket(self, mock_medgemma_client):
        """Test handling of Today time bucket."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Urgent task",
            next_step="Do now",
            time_bucket="Today"
        )

        assert result is not None

    def test_handles_later_bucket(self, mock_medgemma_client):
        """Test handling of Later time bucket."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="Non-urgent task",
            next_step="Do later",
            time_bucket="Later"
        )

        assert result is not None

    def test_strips_whitespace(self, mock_medgemma_client):
        """Test that input values are stripped."""
        result = interpret_caregap(
            client=mock_medgemma_client,
            item_text="  Task  ",
            next_step="  Action  ",
            time_bucket="  Today  "
        )

        call_args = mock_medgemma_client.generate.call_args[0][0]
        assert "Task" in call_args

    def test_raises_on_invalid_json_response(self):
        """Test that ValidationError is raised on invalid JSON."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "Not JSON"

        with pytest.raises(ValidationError):
            interpret_caregap(
                client=mock_client,
                item_text="Task",
                next_step="Action",
                time_bucket="Today"
            )

    def test_raises_on_missing_keys(self):
        """Test that ValidationError is raised when keys are missing."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '{"time_bucket": "Today"}'

        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            interpret_caregap(
                client=mock_client,
                item_text="Task",
                next_step="Action",
                time_bucket="Today"
            )

    def test_raises_on_too_many_sentences_in_action_item(self):
        """Test validation of sentence count in action_item."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"time_bucket": "Today", "action_item": "First sentence. Second sentence.", "next_step": "Do it"}'''

        with pytest.raises(ValidationError, match="must be <= 1 sentence"):
            interpret_caregap(
                client=mock_client,
                item_text="Task",
                next_step="Action",
                time_bucket="Today"
            )


class TestCareOutKeys:
    """Tests for CARE_OUT_KEYS constant."""

    def test_contains_required_fields(self):
        """Test that all required output fields are defined."""
        assert "time_bucket" in CARE_OUT_KEYS
        assert "action_item" in CARE_OUT_KEYS
        assert "next_step" in CARE_OUT_KEYS

    def test_has_three_keys(self):
        """Test that exactly 3 keys are defined."""
        assert len(CARE_OUT_KEYS) == 3
