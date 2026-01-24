"""
Golden specification validators for CareMap integration tests.

These validators check that MedGemma outputs conform to safety and
quality requirements defined in the golden specification files.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set


def assert_no_forbidden_terms(
    output: Dict[str, Any],
    forbidden_terms: List[str],
    scenario_id: str,
) -> None:
    """
    Assert that no forbidden terms appear in any output field.

    Forbidden terms are defined per-scenario in golden specs and include:
    - Specific numeric values (e.g., "8.4%", "42 mL/min")
    - Medical jargon (e.g., "cardiomegaly", "effusion")
    - Abbreviations (e.g., "eGFR", "BNP")

    Args:
        output: The MedGemma output dictionary
        forbidden_terms: List of terms that should NOT appear
        scenario_id: For error reporting

    Raises:
        AssertionError: If any forbidden term is found
    """
    # Combine all string values from output
    all_text = " ".join(
        str(v) for v in output.values() if isinstance(v, str)
    ).lower()

    found_forbidden = []
    for term in forbidden_terms:
        # Use word boundary matching for short terms to avoid false positives
        if len(term) <= 3:
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            if re.search(pattern, all_text):
                found_forbidden.append(term)
        else:
            if term.lower() in all_text:
                found_forbidden.append(term)

    assert not found_forbidden, (
        f"[{scenario_id}] Found forbidden terms in output: {found_forbidden}"
    )


def assert_output_structure(
    output: Dict[str, Any],
    expected_keys: Set[str],
    scenario_id: str,
) -> None:
    """
    Assert that output contains exactly the expected keys.

    Args:
        output: The MedGemma output dictionary
        expected_keys: Set of keys that must be present
        scenario_id: For error reporting

    Raises:
        AssertionError: If keys don't match
    """
    actual_keys = set(output.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    assert not missing, f"[{scenario_id}] Missing keys: {missing}"
    assert not extra, f"[{scenario_id}] Unexpected keys: {extra}"


def assert_no_numeric_values(
    output: Dict[str, Any],
    scenario_id: str,
    allow_patterns: List[str] = None,
) -> None:
    """
    Assert that no specific numeric values appear in output.

    Catches patterns like:
    - "8.4%" - percentages
    - "42 mL/min" - lab values with units
    - "2.3 cm" - measurements
    - "890 pg/mL" - lab values

    Args:
        output: The MedGemma output dictionary
        scenario_id: For error reporting
        allow_patterns: Optional list of allowed numeric patterns

    Raises:
        AssertionError: If numeric values found
    """
    allow_patterns = allow_patterns or []

    # Patterns for numeric values we want to catch
    numeric_patterns = [
        r'\d+\.?\d*\s*%',  # Percentages: 8.4%, 50%
        r'\d+\.?\d*\s*(mg|mL|mcg|g|kg|lb|cm|mm|m)',  # Measurements
        r'\d+\.?\d*\s*(mEq|mmol|pg|ng|IU)/[A-Za-z]+',  # Lab units
        r'\d+\.?\d*\s*x\s*\d+',  # Dimensions: 2.3 x 1.5
    ]

    all_text = " ".join(
        str(v) for v in output.values() if isinstance(v, str)
    )

    found_numeric = []
    for pattern in numeric_patterns:
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        for match in matches:
            # Check if this match is in the allow list
            if not any(re.search(allow, match) for allow in allow_patterns):
                found_numeric.append(match)

    # Also catch standalone numbers that look like lab values
    standalone = re.findall(r'\b\d{2,4}\.?\d*\b', all_text)
    for num in standalone:
        # Filter out likely years or common non-lab numbers
        if float(num) > 100 and float(num) < 2020:
            found_numeric.append(num)

    assert not found_numeric, (
        f"[{scenario_id}] Found numeric values in output: {found_numeric}"
    )


def assert_non_empty_values(
    output: Dict[str, Any],
    scenario_id: str,
    required_fields: List[str] = None,
) -> None:
    """
    Assert that output fields contain meaningful content.

    Args:
        output: The MedGemma output dictionary
        scenario_id: For error reporting
        required_fields: Fields that must be non-empty (default: all string fields)

    Raises:
        AssertionError: If any required field is empty
    """
    if required_fields is None:
        required_fields = [k for k, v in output.items() if isinstance(v, str)]

    empty_fields = []
    for field in required_fields:
        value = output.get(field, "")
        if isinstance(value, str) and not value.strip():
            empty_fields.append(field)
        elif isinstance(value, list) and len(value) == 0:
            empty_fields.append(field)

    assert not empty_fields, (
        f"[{scenario_id}] Empty required fields: {empty_fields}"
    )


def assert_plain_language(
    output: Dict[str, Any],
    scenario_id: str,
    jargon_terms: List[str] = None,
) -> None:
    """
    Assert that output uses plain language (no medical jargon).

    Args:
        output: The MedGemma output dictionary
        scenario_id: For error reporting
        jargon_terms: Additional jargon terms to check

    Raises:
        AssertionError: If jargon found
    """
    # Common medical jargon that should be avoided
    default_jargon = [
        "etiology", "prognosis", "differential", "contraindicated",
        "prophylaxis", "idiopathic", "sequelae", "comorbidity",
        "exacerbation", "hemodynamic", "perfusion", "ischemia",
    ]

    all_jargon = default_jargon + (jargon_terms or [])

    all_text = " ".join(
        str(v) for v in output.values() if isinstance(v, str)
    ).lower()

    found_jargon = [term for term in all_jargon if term.lower() in all_text]

    assert not found_jargon, (
        f"[{scenario_id}] Found medical jargon: {found_jargon}"
    )
