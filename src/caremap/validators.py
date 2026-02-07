

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def extract_first_json_object(text: str) -> str:
    """
    Extract the first JSON object from a string.

    Many models add extra words or echo the prompt. We enforce JSON-only by extracting
    the first {...} block with proper brace matching for nested objects.
    """
    s = (text or "").strip()

    # Find the first opening brace
    start = s.find("{")
    if start == -1:
        raise ValidationError("No JSON object found in model output.")

    # Count braces to find matching close
    depth = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(s[start:], start=start):
        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    raise ValidationError("No valid JSON object found (unmatched braces).")


def parse_json_strict(text: str) -> dict[str, Any]:
    """
    Parse a single JSON object from a model output string.

    Raises ValidationError if JSON is missing/invalid or if the top-level is not an object.
    """
    raw = extract_first_json_object(text)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}") from e

    if not isinstance(obj, dict):
        raise ValidationError("Expected a single JSON object (dictionary).")
    return obj


def require_exact_keys(obj: dict[str, Any], keys: list[str]) -> None:
    """
    Ensure the output contains exactly the expected keys (no missing, no extras).
    """
    got = set(obj.keys())
    expected = set(keys)
    if got != expected:
        raise ValidationError(
            f"JSON keys mismatch. Expected exactly {sorted(expected)} but got {sorted(got)}"
        )


def require_keys_with_defaults(
    obj: dict[str, Any],
    keys: list[str],
    default: str = "Not specified — confirm with care team.",
) -> None:
    """
    Ensure the output contains the expected keys, filling missing ones with a safe default.

    Strips any extra keys not in the expected list.
    """
    for key in keys:
        if key not in obj or not isinstance(obj.get(key), str) or not obj[key].strip():
            obj[key] = default
    for extra in set(obj.keys()) - set(keys):
        del obj[extra]


def require_non_empty_str(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Field '{field}' must be a non-empty string.")


def require_max_sentences(value: str, field: str, max_sentences: int) -> None:
    """
    Rough sentence counter to enforce 'one sentence max' style constraints.

    We split on '.', '!', '?' boundaries. This is intentionally simple and deterministic.
    """
    text = (value or "").strip()
    if not text:
        # Allow empty strings for optional fields like important_note.
        return
    parts = [p for p in re.split(r"[.!?](?:\s+|$)", text) if p.strip()]
    if len(parts) > max_sentences:
        raise ValidationError(f"Field '{field}' must be <= {max_sentences} sentence(s).")


def require_one_question(value: str, field: str) -> None:
    """
    Ensure the field contains exactly one question mark.
    (Caregiver prompt asks for a single question to ask the doctor.)
    """
    text = (value or "").strip()
    q = text.count("?")
    if q != 1:
        raise ValidationError(f"Field '{field}' must contain exactly one question mark ('?').")