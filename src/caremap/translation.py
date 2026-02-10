"""
Translation module for CareMap multilingual support.

Uses Meta's NLLB-200 model to translate caregiver-friendly JSON
into multiple languages with back-translation for validation.

Safety-critical design:
- Preserves medication names verbatim
- Preserves timing strings verbatim
- Validates negations are not dropped or inverted
- Detects if new medical advice appears in translation
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


# NLLB-200 language codes
LANGUAGE_CODES = {
    "english": "eng_Latn",
    "bengali": "ben_Beng",
    "spanish": "spa_Latn",
    "hindi": "hin_Deva",
    "portuguese": "por_Latn",  # Brazil, Portugal
    "chinese_traditional": "zho_Hant",
    "chinese_simplified": "zho_Hans",
    "tamil": "tam_Taml",  # South India, Sri Lanka
    "telugu": "tel_Telu",  # South India
    "marathi": "mar_Deva",  # Western India
}

# Language display names for UI
LANGUAGE_NAMES = {
    "eng_Latn": "English",
    "ben_Beng": "বাংলা (Bengali)",
    "spa_Latn": "Español (Spanish)",
    "hin_Deva": "हिन्दी (Hindi)",
    "por_Latn": "Português (Portuguese)",
    "zho_Hant": "繁體中文 (Traditional Chinese)",
    "zho_Hans": "简体中文 (Simplified Chinese)",
    "tam_Taml": "தமிழ் (Tamil)",
    "tel_Telu": "తెలుగు (Telugu)",
    "mar_Deva": "मराठी (Marathi)",
}

# Fields that should NOT be translated (preserve verbatim)
PRESERVE_VERBATIM_FIELDS = {
    "medication",  # Drug names must stay in English/original
    "when_to_give",  # Timing like "8 AM", "twice daily" - keep exact
    "time_bucket",  # "Today", "This Week", "Later" - categorical
}

# Negation patterns that must be preserved in translation
NEGATION_PATTERNS = [
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bnot\b",
    r"\bnever\b",
    r"\bavoid\b",
    r"\bstop\b",
    r"\bno\b",
    r"\bwithout\b",
]

# Warning indicator phrases (must not be dropped)
# Note: "not" is broad but needed to catch "should not", "must not", etc.
WARNING_INDICATORS = [
    "warning",
    "caution",
    "alert",
    "danger",
    "risk",
    "avoid",
    "do not",
    "don't",
    "not",  # Catches "should not", "must not", "cannot"
    "never",
    "stop taking",
    "call doctor",
    "contact doctor",  # Paraphrase of "call doctor"
    "call 911",
    "emergency",
    "serious",
]

# Medical advice phrases that should NOT appear in translation if not in original
FORBIDDEN_NEW_ADVICE = [
    r"\btake \d+ (mg|ml|tablet|pill)",  # Specific dosages
    r"\bincrease.*(dose|dosage)",
    r"\bdecrease.*(dose|dosage)",
    r"\bstop taking",
    r"\bstart taking",
    r"\bdiagnos",
    r"\btreat(ment|ing)?\b",
    r"\bprescri",
]


def pick_device() -> torch.device:
    """Pick best available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class NLLBTranslator:
    """
    NLLB-200 translator with back-translation support for validation.
    """

    def __init__(
        self,
        model_id: str = "facebook/nllb-200-distilled-600M",
        device: Optional[str] = None,
    ) -> None:
        self.model_id = model_id
        self.device = torch.device(device) if device else pick_device()

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        ).to(self.device)
        self.model.eval()

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        max_length: int = 256,
    ) -> str:
        """Translate text from source to target language."""
        if not text or not text.strip():
            return text

        self.tokenizer.src_lang = source_lang
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(self.device)

        with torch.no_grad():
            generated = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(target_lang),
                max_length=max_length,
                num_beams=5,
                early_stopping=True,
            )

        return self.tokenizer.decode(generated[0], skip_special_tokens=True)

    def translate_to(self, text: str, target_lang: str) -> str:
        """Translate from English to target language."""
        return self.translate(text, "eng_Latn", target_lang)

    def back_translate(self, text: str, source_lang: str) -> str:
        """Translate back to English from source language."""
        return self.translate(text, source_lang, "eng_Latn")


@dataclass
class TranslationResult:
    """Result of translating a JSON object to a target language."""

    original: Dict[str, Any]
    translated: Dict[str, Any]
    back_translated: Dict[str, Any]
    target_lang: str
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.validation_errors) == 0


def translate_json_object(
    translator: NLLBTranslator,
    obj: Dict[str, Any],
    target_lang: str,
    preserve_fields: Optional[Set[str]] = None,
) -> TranslationResult:
    """
    Translate a MedGemma-generated JSON object to target language.

    Args:
        translator: NLLB translator instance
        obj: JSON object with string fields to translate
        target_lang: Target language code (e.g., "ben_Beng", "spa_Latn")
        preserve_fields: Fields to preserve verbatim (not translate)

    Returns:
        TranslationResult with original, translated, and back-translated versions
    """
    preserve = preserve_fields or PRESERVE_VERBATIM_FIELDS

    translated = {}
    back_translated = {}

    for key, value in obj.items():
        if not isinstance(value, str):
            # Non-string values pass through unchanged
            translated[key] = value
            back_translated[key] = value
            continue

        if key in preserve or not value.strip():
            # Preserve verbatim fields
            translated[key] = value
            back_translated[key] = value
        else:
            # Translate string fields
            trans = translator.translate_to(value, target_lang)
            back = translator.back_translate(trans, target_lang)
            translated[key] = trans
            back_translated[key] = back

    return TranslationResult(
        original=obj,
        translated=translated,
        back_translated=back_translated,
        target_lang=target_lang,
    )


# =============================================================================
# Validation Functions
# =============================================================================


def validate_structure(result: TranslationResult) -> List[str]:
    """
    Validate structural invariants are preserved.

    Protects against:
    - Keys being added or removed during translation
    - JSON structure corruption
    """
    errors = []

    orig_keys = set(result.original.keys())
    trans_keys = set(result.translated.keys())
    back_keys = set(result.back_translated.keys())

    # Check no keys were added or removed
    if trans_keys != orig_keys:
        missing = orig_keys - trans_keys
        extra = trans_keys - orig_keys
        if missing:
            errors.append(f"Keys missing in translation: {missing}")
        if extra:
            errors.append(f"Extra keys added in translation: {extra}")

    if back_keys != orig_keys:
        missing = orig_keys - back_keys
        extra = back_keys - orig_keys
        if missing:
            errors.append(f"Keys missing in back-translation: {missing}")
        if extra:
            errors.append(f"Extra keys added in back-translation: {extra}")

    return errors


def validate_preserved_fields(result: TranslationResult) -> List[str]:
    """
    Validate that preserve-verbatim fields were not modified.

    Protects against:
    - Medication names being translated/corrupted
    - Timing strings being altered
    """
    errors = []

    for field in PRESERVE_VERBATIM_FIELDS:
        if field not in result.original:
            continue

        orig_val = result.original[field]
        trans_val = result.translated.get(field)

        if orig_val != trans_val:
            errors.append(
                f"Preserved field '{field}' was modified: "
                f"'{orig_val}' -> '{trans_val}'"
            )

    return errors


def validate_negations_preserved(result: TranslationResult) -> List[str]:
    """
    Validate that negations are preserved in back-translation.

    Protects against:
    - "Do not take with alcohol" becoming "Take with alcohol"
    - "Never skip doses" becoming "Skip doses"
    - Critical safety negations being dropped or inverted

    Allows legitimate paraphrasing:
    - "Do not" -> "Don't" is acceptable
    - "Never" -> "Avoid" is acceptable
    - We check if ANY negation exists, not the exact same form
    """
    errors = []

    for key, orig_val in result.original.items():
        if not isinstance(orig_val, str):
            continue

        back_val = result.back_translated.get(key, "")
        orig_lower = orig_val.lower()
        back_lower = back_val.lower()

        # Check if original has ANY negation
        orig_has_any_negation = any(
            re.search(pattern, orig_lower) for pattern in NEGATION_PATTERNS
        )

        if not orig_has_any_negation:
            continue

        # If original has negation, back-translation must have SOME negation
        # (we allow paraphrasing, e.g., "do not" -> "don't" or "avoid")
        back_has_any_negation = any(
            re.search(pattern, back_lower) for pattern in NEGATION_PATTERNS
        )

        if not back_has_any_negation:
            # No negation found at all in back-translation - this is dangerous
            errors.append(
                f"Negation completely lost in '{key}': "
                f"Original has negation but back-translation has none. "
                f"Original: '{orig_val[:100]}...' "
                f"Back: '{back_val[:100]}...'"
            )

    return errors


def validate_warnings_preserved(result: TranslationResult) -> List[str]:
    """
    Validate that warning/caution indicators are not dropped.

    Protects against:
    - Important safety warnings being lost in translation
    - "Call doctor immediately" being dropped

    Allows legitimate paraphrasing:
    - "call doctor" -> "contact doctor" is acceptable
    - We check if the field had warnings AND still has SOME warning indicator
    """
    errors = []

    for key, orig_val in result.original.items():
        if not isinstance(orig_val, str):
            continue

        back_val = result.back_translated.get(key, "")
        orig_lower = orig_val.lower()
        back_lower = back_val.lower()

        # Check if original has ANY warning indicator
        orig_has_warning = any(indicator in orig_lower for indicator in WARNING_INDICATORS)

        if not orig_has_warning:
            continue

        # If original has warning content, back-translation should have SOME warning indicator
        # (we allow paraphrasing - different indicator words are fine)
        back_has_warning = any(indicator in back_lower for indicator in WARNING_INDICATORS)

        if not back_has_warning:
            # No warning indicator at all - might be lost
            errors.append(
                f"Warning content may be lost in '{key}': "
                f"Original has warning indicators but back-translation has none. "
                f"Original: '{orig_val[:100]}...' "
                f"Back: '{back_val[:100]}...'"
            )

    return errors


def validate_no_new_medical_advice(result: TranslationResult) -> List[str]:
    """
    Validate that translation didn't introduce new medical advice.

    Protects against:
    - Hallucinated dosage instructions appearing in translation
    - New treatment recommendations being added
    - Model adding medical advice not in original
    """
    errors = []

    for key, orig_val in result.original.items():
        if not isinstance(orig_val, str):
            continue

        back_val = result.back_translated.get(key, "")
        orig_lower = orig_val.lower()
        back_lower = back_val.lower()

        for pattern in FORBIDDEN_NEW_ADVICE:
            orig_has = bool(re.search(pattern, orig_lower))
            back_has = bool(re.search(pattern, back_lower))

            if back_has and not orig_has:
                # New medical advice appeared in back-translation
                errors.append(
                    f"New medical advice may have appeared in '{key}': "
                    f"Pattern '{pattern}' found in back-translation but not original. "
                    f"Back: '{back_val[:100]}...'"
                )

    return errors


def validate_meaning_preserved(result: TranslationResult) -> List[str]:
    """
    Basic smoke test for meaning preservation using back-translation.

    Does NOT require exact match (paraphrasing is acceptable).
    Looks for major meaning loss indicators.

    Protects against:
    - Complete meaning inversion
    - Major content loss (back-translation much shorter)
    - Gibberish output
    """
    warnings = []

    for key, orig_val in result.original.items():
        if not isinstance(orig_val, str) or key in PRESERVE_VERBATIM_FIELDS:
            continue

        back_val = result.back_translated.get(key, "")

        # Check for major length discrepancy (could indicate lost content)
        orig_len = len(orig_val)
        back_len = len(back_val)

        if orig_len > 20 and back_len < orig_len * 0.3:
            warnings.append(
                f"Significant content may be lost in '{key}': "
                f"Original {orig_len} chars, back-translation {back_len} chars"
            )

        # Check for empty back-translation of non-empty original
        if orig_val.strip() and not back_val.strip():
            warnings.append(
                f"Back-translation of '{key}' is empty but original was not"
            )

    return warnings


def run_translation_validation(
    result: TranslationResult,
) -> TranslationResult:
    """
    Run all validation checks on a translation result.

    Returns the result with validation_errors and warnings populated.
    """
    errors = []
    warnings = []

    # Structural checks (hard failures)
    errors.extend(validate_structure(result))
    errors.extend(validate_preserved_fields(result))

    # Safety-critical checks (hard failures)
    errors.extend(validate_negations_preserved(result))
    errors.extend(validate_warnings_preserved(result))
    errors.extend(validate_no_new_medical_advice(result))

    # Smoke test checks (warnings, not failures)
    warnings.extend(validate_meaning_preserved(result))

    result.validation_errors = errors
    result.warnings = warnings

    return result
