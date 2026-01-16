"""Validation helpers for golden specification tests.

These functions validate MedGemma outputs against golden specifications,
checking for forbidden terms, correct structure, and appropriate content.
"""
from __future__ import annotations

import re
from typing import Any


class GoldenValidationError(AssertionError):
    """Custom error for golden test validation failures."""

    pass


def check_forbidden_terms(
    output: dict[str, Any],
    forbidden_terms: list[str],
    case_sensitive: bool = True,
) -> list[str]:
    """Check if any forbidden terms appear in the output.

    Args:
        output: Dictionary output from interpretation function
        forbidden_terms: List of terms that should NOT appear
        case_sensitive: Whether to do case-sensitive matching

    Returns:
        List of forbidden terms that were found (empty if none)
    """
    found_terms = []

    # Concatenate all string values from output
    output_text = " ".join(str(v) for v in output.values() if isinstance(v, str))

    for term in forbidden_terms:
        if case_sensitive:
            if term in output_text:
                found_terms.append(term)
        else:
            if term.lower() in output_text.lower():
                found_terms.append(term)

    return found_terms


def assert_no_forbidden_terms(
    output: dict[str, Any],
    forbidden_terms: list[str],
    scenario_id: str,
    case_sensitive: bool = True,
) -> None:
    """Assert that no forbidden terms appear in output.

    Raises:
        GoldenValidationError: If any forbidden terms are found
    """
    found = check_forbidden_terms(output, forbidden_terms, case_sensitive)
    if found:
        raise GoldenValidationError(
            f"[{scenario_id}] Forbidden terms found in output: {found}\n"
            f"Output: {output}"
        )


def assert_output_keys_match(
    output: dict[str, Any],
    expected_keys: list[str],
    scenario_id: str,
) -> None:
    """Assert that output contains exactly the expected keys.

    Raises:
        GoldenValidationError: If keys don't match
    """
    actual_keys = set(output.keys())
    expected_set = set(expected_keys)

    if actual_keys != expected_set:
        missing = expected_set - actual_keys
        extra = actual_keys - expected_set
        raise GoldenValidationError(
            f"[{scenario_id}] Key mismatch.\n"
            f"Missing keys: {missing}\n"
            f"Extra keys: {extra}\n"
            f"Expected: {sorted(expected_set)}\n"
            f"Got: {sorted(actual_keys)}"
        )


def assert_non_empty_string_values(
    output: dict[str, Any],
    keys: list[str],
    scenario_id: str,
) -> None:
    """Assert that specified keys have non-empty string values.

    Raises:
        GoldenValidationError: If any value is empty or not a string
    """
    for key in keys:
        value = output.get(key)
        if not isinstance(value, str):
            raise GoldenValidationError(
                f"[{scenario_id}] Key '{key}' is not a string: {type(value)}"
            )
        if not value.strip():
            raise GoldenValidationError(
                f"[{scenario_id}] Key '{key}' is empty or whitespace-only"
            )


def assert_no_numeric_values(
    output: dict[str, Any],
    scenario_id: str,
    exclude_keys: list[str] | None = None,
) -> None:
    """Assert that output text doesn't contain specific numeric patterns.

    This catches things like "8.4%", "42 mL/min", etc.
    """
    exclude_keys = exclude_keys or []

    # Pattern for medical numeric values: number followed by unit or %
    numeric_pattern = re.compile(
        r"\b\d+\.?\d*\s*(%|mg|mL|mEq|pg|g/dL|mIU|mm|cm|mcg|units?)\b",
        re.IGNORECASE,
    )

    for key, value in output.items():
        if key in exclude_keys:
            continue
        if isinstance(value, str):
            matches = numeric_pattern.findall(value)
            if matches:
                raise GoldenValidationError(
                    f"[{scenario_id}] Numeric value found in '{key}': {value}"
                )


def validate_golden_output(
    output: dict[str, Any],
    expected_keys: list[str],
    forbidden_terms: list[str],
    scenario_id: str,
    check_numerics: bool = True,
) -> None:
    """Comprehensive validation of output against golden specification.

    Performs:
    1. Key structure validation
    2. Non-empty string value validation
    3. Forbidden term checking
    4. Optional numeric value checking
    """
    assert_output_keys_match(output, expected_keys, scenario_id)
    assert_non_empty_string_values(output, expected_keys, scenario_id)
    assert_no_forbidden_terms(output, forbidden_terms, scenario_id)

    if check_numerics:
        assert_no_numeric_values(output, scenario_id)
