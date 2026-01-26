"""
Translation Demo: Test NLLB translation with back-translation validation.

This standalone demo tests the translation safety pipeline without requiring
MedGemma. Uses sample medication data to demonstrate:

1. Translation to multiple languages (Spanish, Hindi, Bengali)
2. Back-translation validation
3. Safety checks (negation preservation, warning preservation)

Run with:
    PYTHONPATH=src .venv/bin/python -m caremap.translation_demo
"""
from __future__ import annotations

from tqdm import tqdm

from .translation import (
    LANGUAGE_CODES,
    LANGUAGE_NAMES,
    NLLBTranslator,
    translate_json_object,
    run_translation_validation,
)


# Sample medication entries (mimicking MedGemma output)
SAMPLE_MEDICATIONS = [
    {
        "medication": "Metformin",
        "what_this_does": "This medicine helps control your blood sugar levels by helping your body use insulin better.",
        "how_to_give": "Give one tablet by mouth twice daily with meals.",
        "watch_out_for": "Do not take if having a CT scan with contrast dye. Stop taking 2 days before any procedure. Watch for stomach upset - take with food to help.",
        "when_to_give": "8 AM, 6 PM",
    },
    {
        "medication": "Warfarin",
        "what_this_does": "This blood thinner helps prevent dangerous blood clots that could cause a stroke.",
        "how_to_give": "Give the exact dose prescribed - check the color of the tablet matches what's expected.",
        "watch_out_for": "Never give aspirin, ibuprofen, or other pain medicines without asking the doctor first - they can cause dangerous bleeding. Watch for unusual bruising or bleeding.",
        "when_to_give": "6 PM",
    },
    {
        "medication": "Furosemide",
        "what_this_does": "This water pill removes extra fluid from the body to help the heart work easier.",
        "how_to_give": "Give one tablet by mouth each morning. The person will need to urinate more often.",
        "watch_out_for": "Weigh the person every morning before breakfast. Call the doctor if weight goes up more than 2-3 pounds overnight - this could mean too much fluid.",
        "when_to_give": "8 AM",
    },
]


def demo_single_translation():
    """Demo translating a single medication entry."""
    print("\n" + "=" * 60)
    print("SINGLE MEDICATION TRANSLATION DEMO")
    print("=" * 60)

    # Initialize translator
    print("\nInitializing NLLB-200 translator...")
    translator = NLLBTranslator()
    print(f"Model: {translator.model_id}")
    print(f"Device: {translator.device}")

    med = SAMPLE_MEDICATIONS[0]  # Metformin
    print(f"\n{'='*60}")
    print(f"ORIGINAL (English): {med['medication']}")
    print(f"{'='*60}")
    print(f"what_this_does: {med['what_this_does']}")
    print(f"watch_out_for: {med['watch_out_for']}")

    # Translate to Spanish
    target_lang = "spanish"
    lang_code = LANGUAGE_CODES[target_lang]
    lang_display = LANGUAGE_NAMES[lang_code]

    print(f"\n{'='*60}")
    print(f"TRANSLATING TO: {lang_display}")
    print(f"{'='*60}")

    result = translate_json_object(translator, med, lang_code)
    result = run_translation_validation(result)

    print(f"\nTRANSLATED:")
    print(f"what_this_does: {result.translated['what_this_does']}")
    print(f"watch_out_for: {result.translated['watch_out_for']}")

    print(f"\nBACK-TRANSLATED (for validation):")
    print(f"what_this_does: {result.back_translated['what_this_does']}")
    print(f"watch_out_for: {result.back_translated['watch_out_for']}")

    print(f"\nVALIDATION RESULT:")
    print(f"Valid: {'Yes' if result.is_valid else 'No'}")

    if result.validation_errors:
        print("Errors:")
        for error in result.validation_errors:
            print(f"  - {error}")

    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.is_valid and not result.warnings:
        print("All safety checks passed!")

    return translator


def demo_all_languages(translator: NLLBTranslator):
    """Demo translating to all supported languages."""
    print("\n" + "=" * 60)
    print("MULTI-LANGUAGE TRANSLATION DEMO")
    print("=" * 60)

    # Test medication with critical warnings
    med = SAMPLE_MEDICATIONS[1]  # Warfarin (has "never", "dangerous")
    print(f"\nSource: {med['medication']}")
    print(f"Critical text: {med['watch_out_for'][:60]}...")

    # Target languages
    languages = ["spanish", "hindi", "bengali", "portuguese", "tamil"]

    results = {}
    for lang_name in tqdm(languages, desc="Translating"):
        if lang_name not in LANGUAGE_CODES:
            continue

        lang_code = LANGUAGE_CODES[lang_name]
        result = translate_json_object(translator, med, lang_code)
        result = run_translation_validation(result)
        results[lang_name] = result

    # Print results table
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"{'Language':<15} {'Valid':<8} {'Errors':<8} {'Warnings'}")
    print("-" * 60)

    for lang_name, result in results.items():
        lang_code = LANGUAGE_CODES[lang_name]
        lang_display = LANGUAGE_NAMES.get(lang_code, lang_name)[:12]
        valid = "Yes" if result.is_valid else "No"
        errors = len(result.validation_errors)
        warnings = len(result.warnings)
        print(f"{lang_display:<15} {valid:<8} {errors:<8} {warnings}")

    # Show sample translations
    print(f"\n{'='*60}")
    print("SAMPLE TRANSLATIONS (watch_out_for field)")
    print(f"{'='*60}")

    for lang_name, result in results.items():
        lang_code = LANGUAGE_CODES[lang_name]
        lang_display = LANGUAGE_NAMES.get(lang_code, lang_name)
        translated = result.translated.get("watch_out_for", "")[:80]
        print(f"\n{lang_display}:")
        print(f"  {translated}...")


def demo_safety_validation(translator: NLLBTranslator):
    """Demo the safety validation catching problems."""
    print("\n" + "=" * 60)
    print("SAFETY VALIDATION DEMO")
    print("=" * 60)

    # All medications have safety-critical content
    print("\nTesting safety-critical content preservation across languages...")

    all_results = []

    for med in SAMPLE_MEDICATIONS:
        print(f"\n{'-'*40}")
        print(f"Testing: {med['medication']}")

        for lang_name in ["spanish", "hindi", "bengali"]:
            lang_code = LANGUAGE_CODES[lang_name]
            result = translate_json_object(translator, med, lang_code)
            result = run_translation_validation(result)

            status = "[PASS]" if result.is_valid else "[FAIL]"
            lang_display = LANGUAGE_NAMES.get(lang_code, lang_name)

            all_results.append({
                "medication": med["medication"],
                "language": lang_display,
                "valid": result.is_valid,
                "errors": len(result.validation_errors),
                "warnings": len(result.warnings),
            })

            if not result.is_valid:
                print(f"  {status} {lang_display}: {result.validation_errors[0][:50]}...")
            elif result.warnings:
                print(f"  {status} {lang_display}: Warning - {result.warnings[0][:40]}...")
            else:
                print(f"  {status} {lang_display}: All checks passed")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    total = len(all_results)
    passed = sum(1 for r in all_results if r["valid"])
    print(f"Total translations: {total}")
    print(f"Passed validation: {passed} ({passed/total*100:.0f}%)")

    if passed < total:
        print("\nFailed translations need review before use!")


def main():
    """Run all demos."""
    print("\n" + "#" * 60)
    print("# CAREMAP TRANSLATION SAFETY DEMO")
    print("# Testing NLLB-200 translation with back-translation validation")
    print("#" * 60)

    # Run single translation demo (also initializes translator)
    translator = demo_single_translation()

    # Run multi-language demo
    demo_all_languages(translator)

    # Run safety validation demo
    demo_safety_validation(translator)

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
