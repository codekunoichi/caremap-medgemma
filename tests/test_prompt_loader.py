"""
Tests for caremap.prompt_loader module.
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from caremap.prompt_loader import (
    PromptRef,
    _repo_root,
    prompts_dir,
    load_prompt,
    fill_prompt,
)


class TestPromptRef:
    """Tests for PromptRef dataclass."""

    def test_creates_prompt_ref(self):
        ref = PromptRef(filename="test.txt")
        assert ref.filename == "test.txt"

    def test_is_frozen(self):
        ref = PromptRef(filename="test.txt")
        with pytest.raises(AttributeError):
            ref.filename = "other.txt"


class TestRepoRoot:
    """Tests for _repo_root function."""

    def test_returns_path(self):
        root = _repo_root()
        assert isinstance(root, Path)

    def test_root_contains_prompts_dir(self):
        root = _repo_root()
        assert (root / "prompts").exists()


class TestPromptsDir:
    """Tests for prompts_dir function."""

    def test_returns_prompts_path(self):
        path = prompts_dir()
        assert path.name == "prompts"
        assert path.exists()


class TestLoadPrompt:
    """Tests for load_prompt function."""

    def test_loads_existing_prompt_by_string(self):
        # Use an actual prompt file that exists
        content = load_prompt("medication_prompt_v1.txt")
        assert "medication" in content.lower() or "MEDICATION" in content

    def test_loads_existing_prompt_by_ref(self):
        ref = PromptRef(filename="medication_prompt_v1.txt")
        content = load_prompt(ref)
        assert len(content) > 0

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError, match="Prompt not found"):
            load_prompt("nonexistent_prompt.txt")

    def test_caches_results(self):
        # Call twice and verify caching works
        content1 = load_prompt("medication_prompt_v1.txt")
        content2 = load_prompt("medication_prompt_v1.txt")
        assert content1 == content2

    def test_loads_lab_prompt(self):
        content = load_prompt("lab_prompt_v1.txt")
        assert "test" in content.lower() or "TEST" in content

    def test_loads_caregap_prompt(self):
        content = load_prompt("caregap_prompt_v1.txt")
        assert len(content) > 0


class TestFillPrompt:
    """Tests for fill_prompt function."""

    def test_fills_single_variable(self):
        template = "Hello {{NAME}}!"
        result = fill_prompt(template, {"NAME": "World"})
        assert result == "Hello World!"

    def test_fills_multiple_variables(self):
        template = "{{GREETING}} {{NAME}}, you are {{AGE}} years old."
        result = fill_prompt(template, {"GREETING": "Hello", "NAME": "Alice", "AGE": "30"})
        assert result == "Hello Alice, you are 30 years old."

    def test_handles_empty_variables(self):
        template = "Name: {{NAME}}"
        result = fill_prompt(template, {"NAME": ""})
        assert result == "Name: "

    def test_leaves_unfilled_variables(self):
        template = "{{FILLED}} and {{UNFILLED}}"
        result = fill_prompt(template, {"FILLED": "yes"})
        assert result == "yes and {{UNFILLED}}"

    def test_handles_no_variables(self):
        template = "No variables here"
        result = fill_prompt(template, {})
        assert result == "No variables here"

    def test_converts_non_string_values(self):
        template = "Count: {{COUNT}}"
        result = fill_prompt(template, {"COUNT": 42})
        assert result == "Count: 42"

    def test_replaces_all_occurrences(self):
        template = "{{X}} and {{X}} and {{X}}"
        result = fill_prompt(template, {"X": "A"})
        assert result == "A and A and A"

    def test_handles_multiline_template(self):
        template = """Line 1: {{VAR1}}
Line 2: {{VAR2}}
Line 3: {{VAR1}}"""
        result = fill_prompt(template, {"VAR1": "A", "VAR2": "B"})
        assert "Line 1: A" in result
        assert "Line 2: B" in result
        assert "Line 3: A" in result
