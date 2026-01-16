"""
Tests for caremap.validators module.
"""
from __future__ import annotations

import pytest

from caremap.validators import (
    ValidationError,
    extract_first_json_object,
    parse_json_strict,
    require_exact_keys,
    require_non_empty_str,
    require_max_sentences,
    require_one_question,
)


class TestExtractFirstJsonObject:
    """Tests for extract_first_json_object function."""

    def test_extracts_simple_json(self):
        text = '{"key": "value"}'
        result = extract_first_json_object(text)
        assert result == '{"key": "value"}'

    def test_extracts_json_with_prefix(self):
        text = 'Here is the result: {"key": "value"}'
        result = extract_first_json_object(text)
        assert result == '{"key": "value"}'

    def test_extracts_json_with_suffix(self):
        text = '{"key": "value"} and some more text'
        result = extract_first_json_object(text)
        assert '{"key": "value"}' in result

    def test_extracts_nested_json(self):
        text = '{"outer": {"inner": "value"}}'
        result = extract_first_json_object(text)
        assert "outer" in result and "inner" in result

    def test_raises_on_no_json(self):
        with pytest.raises(ValidationError, match="No JSON object found"):
            extract_first_json_object("no json here")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValidationError, match="No JSON object found"):
            extract_first_json_object("")

    def test_raises_on_none(self):
        with pytest.raises(ValidationError, match="No JSON object found"):
            extract_first_json_object(None)

    def test_handles_whitespace(self):
        text = '   {"key": "value"}   '
        result = extract_first_json_object(text)
        assert '{"key": "value"}' in result


class TestParseJsonStrict:
    """Tests for parse_json_strict function."""

    def test_parses_valid_json(self):
        result = parse_json_strict('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_json_with_extra_text(self):
        result = parse_json_strict('Response: {"key": "value"} done')
        assert result["key"] == "value"

    def test_raises_on_invalid_json(self):
        with pytest.raises(ValidationError, match="Invalid JSON"):
            parse_json_strict('{"key": }')

    def test_extracts_from_array_wrapper(self):
        # The regex extracts the first {...} which may be inside an array
        # This behavior means arrays with objects inside will extract the inner object
        result = parse_json_strict('[{"key": "value"}]')
        assert result["key"] == "value"

    def test_raises_on_array_of_primitives(self):
        # An array without objects should fail
        with pytest.raises(ValidationError, match="No JSON object found"):
            parse_json_strict('[1, 2, 3]')

    def test_parses_complex_object(self):
        json_str = '{"name": "Test", "count": 5, "active": true, "items": ["a", "b"]}'
        result = parse_json_strict(json_str)
        assert result["name"] == "Test"
        assert result["count"] == 5
        assert result["active"] is True
        assert result["items"] == ["a", "b"]


class TestRequireExactKeys:
    """Tests for require_exact_keys function."""

    def test_passes_with_exact_keys(self):
        obj = {"a": 1, "b": 2}
        require_exact_keys(obj, ["a", "b"])  # Should not raise

    def test_raises_on_missing_key(self):
        obj = {"a": 1}
        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            require_exact_keys(obj, ["a", "b"])

    def test_raises_on_extra_key(self):
        obj = {"a": 1, "b": 2, "c": 3}
        with pytest.raises(ValidationError, match="JSON keys mismatch"):
            require_exact_keys(obj, ["a", "b"])

    def test_passes_with_empty_object(self):
        obj = {}
        require_exact_keys(obj, [])  # Should not raise

    def test_order_independent(self):
        obj = {"b": 2, "a": 1}
        require_exact_keys(obj, ["a", "b"])  # Should not raise


class TestRequireNonEmptyStr:
    """Tests for require_non_empty_str function."""

    def test_passes_with_non_empty_string(self):
        require_non_empty_str("hello", "field")  # Should not raise

    def test_raises_on_empty_string(self):
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            require_non_empty_str("", "field")

    def test_raises_on_whitespace_only(self):
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            require_non_empty_str("   ", "field")

    def test_raises_on_none(self):
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            require_non_empty_str(None, "field")

    def test_raises_on_non_string(self):
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            require_non_empty_str(123, "field")


class TestRequireMaxSentences:
    """Tests for require_max_sentences function."""

    def test_passes_with_one_sentence(self):
        require_max_sentences("This is one sentence.", "field", max_sentences=1)

    def test_passes_with_empty_string(self):
        require_max_sentences("", "field", max_sentences=1)  # Empty allowed

    def test_raises_on_too_many_sentences(self):
        with pytest.raises(ValidationError, match="must be <= 1 sentence"):
            require_max_sentences("First sentence. Second sentence.", "field", max_sentences=1)

    def test_passes_with_multiple_allowed(self):
        require_max_sentences("First. Second. Third.", "field", max_sentences=3)

    def test_handles_question_marks(self):
        require_max_sentences("What is this?", "field", max_sentences=1)

    def test_handles_exclamation_marks(self):
        require_max_sentences("Watch out!", "field", max_sentences=1)

    def test_counts_mixed_punctuation(self):
        with pytest.raises(ValidationError, match="must be <= 2 sentence"):
            require_max_sentences("Statement. Question? Exclaim!", "field", max_sentences=2)

    def test_handles_none_input(self):
        require_max_sentences(None, "field", max_sentences=1)  # Should not raise


class TestRequireOneQuestion:
    """Tests for require_one_question function."""

    def test_passes_with_one_question(self):
        require_one_question("What should I ask?", "field")

    def test_raises_on_no_question(self):
        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            require_one_question("This is a statement.", "field")

    def test_raises_on_multiple_questions(self):
        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            require_one_question("First? Second?", "field")

    def test_raises_on_empty_string(self):
        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            require_one_question("", "field")

    def test_handles_none_input(self):
        with pytest.raises(ValidationError, match="must contain exactly one question mark"):
            require_one_question(None, "field")


class TestValidationError:
    """Tests for ValidationError class."""

    def test_str_representation(self):
        error = ValidationError("Test message")
        assert str(error) == "Test message"

    def test_is_value_error(self):
        error = ValidationError("Test")
        assert isinstance(error, ValueError)
