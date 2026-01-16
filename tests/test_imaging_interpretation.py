"""
Tests for caremap.imaging_interpretation module.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add src to path to allow direct imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import MagicMock, patch
import tempfile

from caremap.imaging_interpretation import (
    interpret_imaging_report,
    interpret_imaging_with_image,
    get_plain_study_type,
    IMAGING_OUT_KEYS,
    STUDY_TYPE_PLAIN_LANGUAGE,
)
from caremap.validators import ValidationError


@pytest.fixture
def mock_imaging_client():
    """Mock client that returns valid imaging interpretation JSON."""
    mock_client = MagicMock()
    mock_client.generate.return_value = '''{"study_type": "Chest CT", "what_was_done": "Pictures were taken of your chest.", "key_finding": "The results look normal. Your doctor will explain the details.", "what_to_ask_doctor": "Do I need any follow-up tests?"}'''
    return mock_client


class TestInterpretImagingReport:
    """Tests for interpret_imaging_report function."""

    def test_returns_dict_with_required_keys(self, mock_imaging_client):
        """Test that output contains all required keys."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="Chest CT",
            report_text="No acute cardiopulmonary abnormality.",
            flag="normal"
        )

        for key in IMAGING_OUT_KEYS:
            assert key in result

    def test_passes_study_type(self, mock_imaging_client):
        """Test that study type is passed correctly."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="Brain MRI",
            report_text="Normal brain MRI.",
            flag="normal"
        )

        mock_imaging_client.generate.assert_called_once()
        call_args = mock_imaging_client.generate.call_args[0][0]
        assert "Brain MRI" in call_args

    def test_passes_report_text(self, mock_imaging_client):
        """Test that report text is passed correctly."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="Chest X-ray",
            report_text="Clear lung fields bilaterally.",
            flag="normal"
        )

        call_args = mock_imaging_client.generate.call_args[0][0]
        assert "Clear lung fields bilaterally" in call_args

    def test_passes_flag(self, mock_imaging_client):
        """Test that flag is passed correctly."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="CT",
            report_text="Findings present.",
            flag="needs_follow_up"
        )

        call_args = mock_imaging_client.generate.call_args[0][0]
        assert "needs_follow_up" in call_args

    def test_handles_empty_report_text(self, mock_imaging_client):
        """Test handling of empty report text."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="MRI",
            report_text="",
            flag="normal"
        )

        assert result is not None

    def test_strips_whitespace(self, mock_imaging_client):
        """Test that input values are stripped."""
        result = interpret_imaging_report(
            client=mock_imaging_client,
            study_type="  Chest CT  ",
            report_text="  Report text  ",
            flag="  normal  "
        )

        call_args = mock_imaging_client.generate.call_args[0][0]
        assert "Chest CT" in call_args

    def test_raises_on_invalid_json_response(self):
        """Test that ValidationError is raised on invalid JSON."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "Not valid JSON"

        with pytest.raises(ValidationError):
            interpret_imaging_report(
                client=mock_client,
                study_type="CT",
                report_text="Test",
                flag="normal"
            )

    def test_raises_on_missing_keys(self):
        """Test that ValidationError is raised when keys are missing."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '{"study_type": "CT"}'

        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            interpret_imaging_report(
                client=mock_client,
                study_type="CT",
                report_text="Test",
                flag="normal"
            )

    def test_raises_on_too_many_sentences_in_what_was_done(self):
        """Test validation of sentence count in what_was_done."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"study_type": "CT", "what_was_done": "First sentence. Second sentence.", "key_finding": "Normal.", "what_to_ask_doctor": "Question?"}'''

        with pytest.raises(ValidationError, match="must be <= 1 sentence"):
            interpret_imaging_report(
                client=mock_client,
                study_type="CT",
                report_text="Test",
                flag="normal"
            )

    def test_raises_on_no_question_mark(self):
        """Test that exactly one question mark is required."""
        mock_client = MagicMock()
        mock_client.generate.return_value = '''{"study_type": "CT", "what_was_done": "Test done.", "key_finding": "Normal.", "what_to_ask_doctor": "No question here"}'''

        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            interpret_imaging_report(
                client=mock_client,
                study_type="CT",
                report_text="Test",
                flag="normal"
            )


class TestInterpretImagingWithImage:
    """Tests for interpret_imaging_with_image function."""

    def test_falls_back_to_text_when_report_available(self, mock_imaging_client):
        """Test that it falls back to text interpretation when report is available."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            result = interpret_imaging_with_image(
                client=mock_imaging_client,
                study_type="Chest CT",
                image_paths=[temp_path],
                report_text="Normal findings.",
                flag="normal"
            )

            assert "study_type" in result
            mock_imaging_client.generate.assert_called_once()
        finally:
            Path(temp_path).unlink()

    def test_raises_on_missing_image_file(self, mock_imaging_client):
        """Test that FileNotFoundError is raised for missing images."""
        with pytest.raises(FileNotFoundError, match="Image not found"):
            interpret_imaging_with_image(
                client=mock_imaging_client,
                study_type="CT",
                image_paths=["/nonexistent/image.png"],
                report_text="",
                flag="normal"
            )

    def test_returns_placeholder_when_no_report_and_no_multimodal(self, mock_imaging_client):
        """Test placeholder response when no report text and no multimodal support."""
        # Disable multimodal support
        mock_imaging_client.supports_multimodal = False

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            result = interpret_imaging_with_image(
                client=mock_imaging_client,
                study_type="Brain MRI",
                image_paths=[temp_path],
                report_text="",  # No report text
                flag="normal"
            )

            assert result["study_type"] == "Brain MRI"
            assert "ask your doctor" in result["key_finding"].lower()
        finally:
            Path(temp_path).unlink()

    def test_uses_multimodal_when_enabled(self, mock_imaging_client):
        """Test that multimodal pipeline is used when client supports it."""
        # Enable multimodal support
        mock_imaging_client.supports_multimodal = True
        mock_imaging_client.generate_with_images.return_value = '''{"study_type": "Brain MRI", "what_was_done": "MRI scan of the brain.", "key_finding": "The results look normal.", "what_to_ask_doctor": "Do I need follow-up?"}'''

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            result = interpret_imaging_with_image(
                client=mock_imaging_client,
                study_type="Brain MRI",
                image_paths=[temp_path],
                report_text="",  # No report text, use images
                flag="normal"
            )

            assert result["study_type"] == "Brain MRI"
            mock_imaging_client.generate_with_images.assert_called_once()
        finally:
            Path(temp_path).unlink()


class TestGetPlainStudyType:
    """Tests for get_plain_study_type function."""

    def test_converts_ct(self):
        result = get_plain_study_type("CT")
        assert "CT scan" in result

    def test_converts_mri(self):
        result = get_plain_study_type("MRI")
        assert "MRI scan" in result

    def test_converts_chest_xray(self):
        result = get_plain_study_type("Chest X-ray")
        assert "X-ray" in result

    def test_handles_unknown_type(self):
        result = get_plain_study_type("Unknown Study")
        assert "Unknown Study scan" in result

    def test_strips_whitespace(self):
        result = get_plain_study_type("  CT  ")
        # After strip, "CT" should match
        assert "scan" in result


class TestImagingOutKeys:
    """Tests for IMAGING_OUT_KEYS constant."""

    def test_contains_required_fields(self):
        assert "study_type" in IMAGING_OUT_KEYS
        assert "what_was_done" in IMAGING_OUT_KEYS
        assert "key_finding" in IMAGING_OUT_KEYS
        assert "what_to_ask_doctor" in IMAGING_OUT_KEYS

    def test_has_four_keys(self):
        assert len(IMAGING_OUT_KEYS) == 4


class TestStudyTypePlainLanguage:
    """Tests for STUDY_TYPE_PLAIN_LANGUAGE mapping."""

    def test_common_study_types_mapped(self):
        assert "CT" in STUDY_TYPE_PLAIN_LANGUAGE
        assert "MRI" in STUDY_TYPE_PLAIN_LANGUAGE
        assert "X-ray" in STUDY_TYPE_PLAIN_LANGUAGE
        assert "Chest CT" in STUDY_TYPE_PLAIN_LANGUAGE
        assert "Brain MRI" in STUDY_TYPE_PLAIN_LANGUAGE

    def test_mappings_are_plain_language(self):
        for study_type, plain in STUDY_TYPE_PLAIN_LANGUAGE.items():
            # Plain language should be longer and more descriptive
            assert len(plain) >= len(study_type)
