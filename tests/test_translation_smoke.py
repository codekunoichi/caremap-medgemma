"""
Smoke tests for multilingual translation of caregiver-friendly JSON.

These tests validate translation integrity and caregiver safety:
1. Structural invariants (JSON valid, keys preserved)
2. Meaning-critical invariants (medication names, timing, negations, warnings)
3. Back-translation smoke test (detect major meaning loss)

This is a SAFETY smoke test, not a linguistic evaluation framework.
Legitimate paraphrasing is acceptable; we only catch major failures.

Run tests:
    pytest tests/test_translation_smoke.py -v

    # Run with real NLLB model (slow, requires model download)
    pytest tests/test_translation_smoke.py -v -m "not mock"

    # Run only with mocked translator (fast)
    pytest tests/test_translation_smoke.py -v -m "mock"
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# =============================================================================
# Test Fixtures - Sample MedGemma Output
# =============================================================================


@pytest.fixture
def sample_medication_json() -> Dict[str, Any]:
    """Sample MedGemma medication interpretation output."""
    return {
        "medication": "Metformin 500mg",  # Should be preserved verbatim
        "why_it_matters": "This medicine helps control blood sugar levels. It is important for managing diabetes.",
        "when_to_give": "Twice daily with meals",  # Should be preserved verbatim
        "important_note": "Do not skip doses. Take at the same time each day.",
    }


@pytest.fixture
def sample_lab_json() -> Dict[str, Any]:
    """Sample MedGemma lab interpretation output."""
    return {
        "what_was_checked": "This test measures the average blood sugar over the past few months.",
        "what_it_means": "The results show that blood sugar control needs follow-up. This does not mean anything is wrong, but your doctor will want to discuss it.",
        "what_to_ask_doctor": "What can we do to improve blood sugar control?",
    }


@pytest.fixture
def sample_caregap_json() -> Dict[str, Any]:
    """Sample MedGemma care gap interpretation output."""
    return {
        "time_bucket": "Today",  # Should be preserved verbatim
        "action_item": "Schedule a blood test at the clinic.",
        "next_step": "Call the doctor's office to make an appointment.",
    }


@pytest.fixture
def sample_medication_with_warning() -> Dict[str, Any]:
    """Medication with safety warning - negation must be preserved."""
    return {
        "medication": "Warfarin 5mg",
        "why_it_matters": "This blood thinner helps prevent dangerous blood clots.",
        "when_to_give": "Once daily at bedtime",
        "important_note": "Do not take with aspirin or ibuprofen. Avoid alcohol. Call your doctor immediately if you notice unusual bleeding or bruising.",
    }


@pytest.fixture
def sample_drug_interaction_json() -> Dict[str, Any]:
    """Drug interaction warning - critical safety content."""
    return {
        "medication": "Lisinopril 10mg",
        "why_it_matters": "This medicine helps protect kidneys and control blood pressure.",
        "when_to_give": "Daily in the morning",
        "important_note": "Do not combine with potassium supplements without doctor approval. Never use salt substitutes containing potassium.",
    }


# =============================================================================
# Mock Translator for Fast Unit Tests
# =============================================================================


class MockNLLBTranslator:
    """
    Mock translator that simulates translation behavior for testing.

    Simulates realistic translation scenarios including:
    - Basic translation (adds target language marker)
    - Back-translation (returns paraphrased English)
    """

    def __init__(self):
        self.call_count = 0

    def translate_to(self, text: str, target_lang: str) -> str:
        """Simulate forward translation."""
        self.call_count += 1
        if not text:
            return text
        # Simulate translation by adding language marker
        lang_marker = {"ben_Beng": "[BN]", "spa_Latn": "[ES]"}.get(target_lang, "[??]")
        return f"{lang_marker} {text}"

    def back_translate(self, text: str, source_lang: str) -> str:
        """Simulate back-translation with realistic paraphrasing."""
        self.call_count += 1
        if not text:
            return text

        # Strip the language marker we added
        for marker in ["[BN] ", "[ES] ", "[??] "]:
            if text.startswith(marker):
                text = text[len(marker) :]
                break

        # Simulate paraphrasing (acceptable variation)
        paraphrases = {
            "Do not skip doses": "Don't miss any doses",
            "Take at the same time each day": "Take it at a consistent time daily",
            "Do not take with aspirin": "Avoid taking with aspirin",
            "Call your doctor immediately": "Contact your doctor right away",
        }

        result = text
        for orig, para in paraphrases.items():
            if orig in result:
                result = result.replace(orig, para)

        return result


class MockTranslatorDropsNegation(MockNLLBTranslator):
    """Mock translator that incorrectly drops negations (should fail validation)."""

    def back_translate(self, text: str, source_lang: str) -> str:
        result = super().back_translate(text, source_lang)
        # Simulate dangerous bug: dropping "do not"
        return result.replace("Don't ", "").replace("do not ", "").replace("Do not ", "")


class MockTranslatorDropsWarning(MockNLLBTranslator):
    """Mock translator that drops warning content (should fail validation)."""

    def back_translate(self, text: str, source_lang: str) -> str:
        result = super().back_translate(text, source_lang)
        # Simulate dangerous bug: dropping call doctor warnings
        if "doctor" in result.lower():
            return "Take as directed."
        return result


class MockTranslatorAddsAdvice(MockNLLBTranslator):
    """Mock translator that hallucinates medical advice (should fail validation)."""

    def back_translate(self, text: str, source_lang: str) -> str:
        result = super().back_translate(text, source_lang)
        # Simulate dangerous bug: adding dosage advice
        if "blood sugar" in result.lower():
            return result + " Increase dose to 1000mg if needed."
        return result


# =============================================================================
# Import translation module (with fallback for when NLLB not installed)
# =============================================================================


try:
    from caremap.translation import (
        PRESERVE_VERBATIM_FIELDS,
        TranslationResult,
        run_translation_validation,
        translate_json_object,
        validate_negations_preserved,
        validate_no_new_medical_advice,
        validate_preserved_fields,
        validate_structure,
        validate_warnings_preserved,
    )

    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False


# =============================================================================
# Unit Tests with Mock Translator (Fast)
# =============================================================================


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestTranslationStructure:
    """Test structural invariants are preserved."""

    def test_keys_preserved_in_translation(self, sample_medication_json):
        """Verify all keys are preserved through translation cycle."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        errors = validate_structure(result)
        assert len(errors) == 0, f"Structure errors: {errors}"

        # Verify exact key match
        assert set(result.translated.keys()) == set(sample_medication_json.keys())
        assert set(result.back_translated.keys()) == set(sample_medication_json.keys())

    def test_no_extra_keys_added(self, sample_lab_json):
        """Verify translation doesn't add extra keys."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_lab_json, "spa_Latn")

        errors = validate_structure(result)
        assert len(errors) == 0

    def test_empty_values_handled(self):
        """Verify empty string values don't cause errors."""
        translator = MockNLLBTranslator()
        obj = {
            "medication": "Aspirin",
            "why_it_matters": "",  # Empty
            "when_to_give": "Daily",
            "important_note": "   ",  # Whitespace only
        }

        result = translate_json_object(translator, obj, "ben_Beng")
        errors = validate_structure(result)
        assert len(errors) == 0


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestPreservedFields:
    """Test that verbatim fields are not modified."""

    def test_medication_name_preserved(self, sample_medication_json):
        """Medication names must NOT be translated."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        errors = validate_preserved_fields(result)
        assert len(errors) == 0

        # Verify medication name is exactly the same
        assert result.translated["medication"] == sample_medication_json["medication"]
        assert result.back_translated["medication"] == sample_medication_json["medication"]

    def test_timing_preserved(self, sample_medication_json):
        """Timing strings must NOT be translated."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_json, "spa_Latn")

        # when_to_give should be preserved verbatim
        assert result.translated["when_to_give"] == "Twice daily with meals"

    def test_time_bucket_preserved(self, sample_caregap_json):
        """Time bucket category must NOT be translated."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_caregap_json, "ben_Beng")

        assert result.translated["time_bucket"] == "Today"


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestNegationPreservation:
    """Test that safety-critical negations are preserved."""

    def test_negation_preserved_in_good_translation(self, sample_medication_json):
        """Verify negations are detected in good back-translation."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        errors = validate_negations_preserved(result)
        # Good translator should preserve negations (paraphrased to "Don't")
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_negation_drop_detected(self, sample_medication_json):
        """Detect when translator drops negations (CRITICAL SAFETY BUG)."""
        translator = MockTranslatorDropsNegation()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        errors = validate_negations_preserved(result)
        # Should detect that "do not" was dropped
        assert len(errors) > 0, "Should detect dropped negation"
        assert any("negation" in e.lower() for e in errors)

    def test_warning_with_multiple_negations(self, sample_medication_with_warning):
        """Verify multiple negations in warnings are all checked."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_with_warning, "ben_Beng")

        errors = validate_negations_preserved(result)
        assert len(errors) == 0

    def test_drug_interaction_negations(self, sample_drug_interaction_json):
        """Drug interaction warnings have critical negations."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_drug_interaction_json, "spa_Latn")

        errors = validate_negations_preserved(result)
        assert len(errors) == 0


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestWarningPreservation:
    """Test that warning indicators are not dropped."""

    def test_warning_preserved(self, sample_medication_with_warning):
        """Verify warning indicators are preserved."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_with_warning, "ben_Beng")

        errors = validate_warnings_preserved(result)
        assert len(errors) == 0

    def test_warning_drop_detected(self, sample_medication_with_warning):
        """Detect when translator drops warning content."""
        translator = MockTranslatorDropsWarning()
        result = translate_json_object(translator, sample_medication_with_warning, "ben_Beng")

        errors = validate_warnings_preserved(result)
        # Should detect that "call doctor" was dropped
        assert len(errors) > 0, "Should detect dropped warning"


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestNoNewMedicalAdvice:
    """Test that translation doesn't introduce new medical advice."""

    def test_no_hallucinated_advice(self, sample_lab_json):
        """Verify good translation doesn't add medical advice."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_lab_json, "ben_Beng")

        errors = validate_no_new_medical_advice(result)
        assert len(errors) == 0

    def test_hallucinated_dosage_detected(self, sample_lab_json):
        """Detect when translator hallucinates dosage advice."""
        translator = MockTranslatorAddsAdvice()
        result = translate_json_object(translator, sample_lab_json, "ben_Beng")

        errors = validate_no_new_medical_advice(result)
        assert len(errors) > 0, "Should detect hallucinated advice"
        assert any("advice" in e.lower() or "dose" in e.lower() for e in errors)


@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestFullValidationPipeline:
    """Test the complete validation pipeline."""

    def test_full_validation_passes_good_translation(self, sample_medication_json):
        """Full validation should pass for good translations."""
        translator = MockNLLBTranslator()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        result = run_translation_validation(result)

        assert result.is_valid, f"Validation errors: {result.validation_errors}"
        # Warnings are acceptable (meaning check is a smoke test)

    def test_full_validation_catches_bad_translation(self, sample_medication_json):
        """Full validation should catch dangerous translation bugs."""
        translator = MockTranslatorDropsNegation()
        result = translate_json_object(translator, sample_medication_json, "ben_Beng")

        result = run_translation_validation(result)

        assert not result.is_valid, "Should fail validation when negations dropped"

    def test_validation_both_languages(self, sample_medication_json):
        """Run validation for both Bengali and Spanish."""
        translator = MockNLLBTranslator()

        for lang in ["ben_Beng", "spa_Latn"]:
            result = translate_json_object(translator, sample_medication_json, lang)
            result = run_translation_validation(result)

            assert result.is_valid, f"Validation failed for {lang}: {result.validation_errors}"


# =============================================================================
# Integration Tests with Real NLLB Model (Slow)
# =============================================================================


@pytest.mark.integration
@pytest.mark.skipif(not TRANSLATION_AVAILABLE, reason="Translation module not available")
class TestRealNLLBTranslation:
    """
    Integration tests using real NLLB model.

    These tests are slow (model loading) and require:
    - transformers library
    - torch
    - ~2GB disk space for model weights

    Run with: pytest tests/test_translation_smoke.py -v -m integration
    """

    @pytest.fixture(scope="class")
    def real_translator(self):
        """Load real NLLB translator (shared across tests in class)."""
        from caremap.translation import NLLBTranslator

        return NLLBTranslator(model_id="facebook/nllb-200-distilled-600M")

    def test_bengali_translation_round_trip(self, real_translator, sample_medication_json):
        """Test Bengali translation with real model."""
        result = translate_json_object(real_translator, sample_medication_json, "ben_Beng")
        result = run_translation_validation(result)

        # Real translations may have warnings but shouldn't have hard errors
        assert result.is_valid, f"Errors: {result.validation_errors}"

        # Verify preserved fields
        assert result.translated["medication"] == sample_medication_json["medication"]

    def test_spanish_translation_round_trip(self, real_translator, sample_medication_json):
        """Test Spanish translation with real model."""
        result = translate_json_object(real_translator, sample_medication_json, "spa_Latn")
        result = run_translation_validation(result)

        assert result.is_valid, f"Errors: {result.validation_errors}"

    def test_drug_interaction_translation(self, real_translator, sample_drug_interaction_json):
        """Test safety-critical drug interaction warnings."""
        for lang in ["ben_Beng", "spa_Latn"]:
            result = translate_json_object(real_translator, sample_drug_interaction_json, lang)
            result = run_translation_validation(result)

            # Drug interactions are critical - must pass validation
            assert result.is_valid, f"Drug interaction failed for {lang}: {result.validation_errors}"


# =============================================================================
# Smoke Test Runner (Standalone)
# =============================================================================


def run_smoke_test(use_real_model: bool = False) -> bool:
    """
    Run translation smoke test.

    Args:
        use_real_model: If True, use real NLLB model. If False, use mock.

    Returns:
        True if all tests pass, False otherwise.
    """
    print("=" * 70)
    print("Translation Smoke Test")
    print("=" * 70)

    # Sample data
    test_cases = [
        {
            "name": "Medication",
            "data": {
                "medication": "Metformin 500mg",
                "why_it_matters": "This medicine helps control blood sugar levels.",
                "when_to_give": "Twice daily",
                "important_note": "Do not skip doses.",
            },
        },
        {
            "name": "Drug Interaction Warning",
            "data": {
                "medication": "Warfarin 5mg",
                "why_it_matters": "This blood thinner prevents clots.",
                "when_to_give": "Once daily",
                "important_note": "Do not take with aspirin. Call doctor if bleeding.",
            },
        },
    ]

    languages = ["ben_Beng", "spa_Latn"]

    # Get translator
    if use_real_model:
        from caremap.translation import NLLBTranslator

        print("\nLoading NLLB model...")
        translator = NLLBTranslator()
    else:
        print("\nUsing mock translator...")
        translator = MockNLLBTranslator()

    all_passed = True

    for tc in test_cases:
        print(f"\n{'─' * 70}")
        print(f"Testing: {tc['name']}")
        print("─" * 70)

        for lang in languages:
            lang_name = {"ben_Beng": "Bengali", "spa_Latn": "Spanish"}.get(lang, lang)
            print(f"\n  → {lang_name}:")

            result = translate_json_object(translator, tc["data"], lang)
            result = run_translation_validation(result)

            if result.is_valid:
                print(f"    ✓ PASS - No validation errors")
            else:
                print(f"    ✗ FAIL - Validation errors:")
                for err in result.validation_errors:
                    print(f"      - {err}")
                all_passed = False

            if result.warnings:
                print(f"    ⚠ Warnings:")
                for warn in result.warnings:
                    print(f"      - {warn}")

    print("\n" + "=" * 70)
    if all_passed:
        print("✓ All smoke tests PASSED")
    else:
        print("✗ Some smoke tests FAILED")
    print("=" * 70)

    return all_passed


if __name__ == "__main__":
    import sys

    use_real = "--real" in sys.argv
    success = run_smoke_test(use_real_model=use_real)
    sys.exit(0 if success else 1)
