"""
Multilingual Fridge Sheet Generator for CareMap.

Generates medication fridge sheets in multiple languages for caregivers
in India, Mexico, and South America where access to basic healthcare
advice in native languages is limited.

Supported languages:
- Spanish (Mexico, South America)
- Portuguese (Brazil)
- Hindi (India)
- Bengali (India, Bangladesh)
- Tamil (South India, Sri Lanka)
- Telugu (South India)
- Marathi (Western India)

Run with:
    PYTHONPATH=src .venv/bin/python -m caremap.multilingual_fridge_sheet
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from .translation import (
    LANGUAGE_CODES,
    LANGUAGE_NAMES,
    NLLBTranslator,
    TranslationResult,
    translate_json_object,
    run_translation_validation,
)


# Default target languages for fridge sheets
DEFAULT_TARGET_LANGUAGES = [
    "spanish",      # Mexico, South America
    "hindi",        # India (most spoken)
    "bengali",      # India, Bangladesh
]

# Extended language set for comprehensive coverage
EXTENDED_TARGET_LANGUAGES = [
    "spanish",
    "portuguese",   # Brazil
    "hindi",
    "bengali",
    "tamil",
    "telugu",
    "marathi",
]


@dataclass
class MultilingualFridgeSheet:
    """A fridge sheet in multiple languages with validation results."""

    patient_name: str
    medications: List[Dict[str, Any]]
    english_version: Dict[str, Any]
    translations: Dict[str, TranslationResult] = field(default_factory=dict)

    @property
    def all_valid(self) -> bool:
        """Check if all translations passed validation."""
        return all(t.is_valid for t in self.translations.values())

    @property
    def valid_languages(self) -> List[str]:
        """List languages that passed validation."""
        return [lang for lang, t in self.translations.items() if t.is_valid]

    @property
    def failed_languages(self) -> List[str]:
        """List languages that failed validation."""
        return [lang for lang, t in self.translations.items() if not t.is_valid]


def build_medication_entry(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a single medication entry for the fridge sheet.

    Takes MedGemma interpretation output and formats it for translation.
    """
    return {
        "medication": result.get("medication", "Unknown"),
        "what_this_does": result.get("what_this_does", ""),
        "how_to_give": result.get("how_to_give", ""),
        "watch_out_for": result.get("watch_out_for", ""),
        "when_to_give": result.get("when_to_give", ""),  # Preserved verbatim
    }


def translate_medication_entry(
    translator: NLLBTranslator,
    entry: Dict[str, Any],
    target_lang_code: str,
) -> TranslationResult:
    """
    Translate a single medication entry to target language.

    Uses back-translation validation to ensure safety-critical
    information is preserved.
    """
    result = translate_json_object(
        translator=translator,
        obj=entry,
        target_lang=target_lang_code,
    )

    # Run all validation checks
    return run_translation_validation(result)


def generate_multilingual_fridge_sheet(
    patient_name: str,
    medication_results: List[Dict[str, Any]],
    target_languages: Optional[List[str]] = None,
    translator: Optional[NLLBTranslator] = None,
    show_progress: bool = True,
) -> MultilingualFridgeSheet:
    """
    Generate a multilingual fridge sheet from MedGemma results.

    Args:
        patient_name: Name/nickname for the patient
        medication_results: List of MedGemma interpretation results
        target_languages: Languages to translate to (default: Spanish, Hindi, Bengali)
        translator: Pre-initialized NLLB translator (created if not provided)
        show_progress: Show progress bar during translation

    Returns:
        MultilingualFridgeSheet with all translations and validation results
    """
    languages = target_languages or DEFAULT_TARGET_LANGUAGES

    # Initialize translator if not provided
    if translator is None:
        print("Initializing NLLB translator...")
        translator = NLLBTranslator()

    # Build English version
    medications = []
    for result in medication_results:
        if "error" not in result:
            medications.append(build_medication_entry(result))

    english_version = {
        "patient_name": patient_name,
        "language": "English",
        "medications": medications,
    }

    # Create fridge sheet object
    fridge_sheet = MultilingualFridgeSheet(
        patient_name=patient_name,
        medications=medications,
        english_version=english_version,
    )

    # Translate to each target language
    lang_iter = tqdm(languages, desc="Translating") if show_progress else languages

    for lang_name in lang_iter:
        if lang_name not in LANGUAGE_CODES:
            print(f"Warning: Unknown language '{lang_name}', skipping")
            continue

        lang_code = LANGUAGE_CODES[lang_name]

        # Translate all medications
        translated_meds = []
        all_valid = True
        all_errors = []
        all_warnings = []

        for med in medications:
            result = translate_medication_entry(translator, med, lang_code)
            translated_meds.append(result.translated)

            if not result.is_valid:
                all_valid = False
                all_errors.extend(result.validation_errors)
            all_warnings.extend(result.warnings)

        # Build combined translation result
        combined = TranslationResult(
            original={"medications": medications},
            translated={"medications": translated_meds},
            back_translated={},  # Individual back-translations in each med result
            target_lang=lang_code,
            validation_errors=all_errors,
            warnings=all_warnings,
        )

        fridge_sheet.translations[lang_name] = combined

    return fridge_sheet


def format_fridge_sheet_text(
    fridge_sheet: MultilingualFridgeSheet,
    language: str = "english",
) -> str:
    """
    Format fridge sheet as printable text for a specific language.

    Args:
        fridge_sheet: The multilingual fridge sheet
        language: Language to output (english or one of the translated languages)

    Returns:
        Formatted text suitable for printing
    """
    lines = []

    if language == "english":
        lang_display = "English"
        medications = fridge_sheet.medications
    else:
        if language not in fridge_sheet.translations:
            raise ValueError(f"Language '{language}' not in translations")

        lang_code = LANGUAGE_CODES.get(language, language)
        lang_display = LANGUAGE_NAMES.get(lang_code, language)

        translation = fridge_sheet.translations[language]
        medications = translation.translated.get("medications", [])

    # Header
    lines.append("=" * 60)
    lines.append(f"MEDICATION FRIDGE SHEET FOR {fridge_sheet.patient_name.upper()}")
    lines.append(f"Language: {lang_display}")
    lines.append("=" * 60)
    lines.append("")

    # Each medication
    for med in medications:
        med_name = med.get("medication", "Unknown")
        lines.append(f"[*] {med_name}")

        if med.get("what_this_does"):
            lines.append(f"    What it does: {med['what_this_does']}")

        if med.get("how_to_give"):
            lines.append(f"    How to give: {med['how_to_give']}")

        if med.get("watch_out_for"):
            lines.append(f"    Watch out: {med['watch_out_for']}")

        if med.get("when_to_give"):
            lines.append(f"    When: {med['when_to_give']}")

        lines.append("")

    # Footer
    lines.append("=" * 60)
    lines.append("Always contact your care team with questions!")
    lines.append("=" * 60)

    return "\n".join(lines)


def print_validation_report(fridge_sheet: MultilingualFridgeSheet) -> None:
    """Print validation report for all translations."""
    print(f"\n{'='*60}")
    print("TRANSLATION VALIDATION REPORT")
    print(f"{'='*60}")

    for lang_name, translation in fridge_sheet.translations.items():
        lang_code = LANGUAGE_CODES.get(lang_name, lang_name)
        lang_display = LANGUAGE_NAMES.get(lang_code, lang_name)

        status = "[PASS]" if translation.is_valid else "[FAIL]"
        print(f"\n{status} {lang_display}")

        if translation.validation_errors:
            print("  Errors:")
            for error in translation.validation_errors:
                print(f"    - {error[:80]}...")

        if translation.warnings:
            print("  Warnings:")
            for warning in translation.warnings:
                print(f"    - {warning[:80]}...")

        if translation.is_valid and not translation.warnings:
            print("  All safety checks passed")

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(fridge_sheet.valid_languages)}/{len(fridge_sheet.translations)} languages passed")
    if fridge_sheet.failed_languages:
        print(f"Failed: {', '.join(fridge_sheet.failed_languages)}")
    print(f"{'='*60}")


def save_multilingual_output(
    fridge_sheet: MultilingualFridgeSheet,
    output_dir: Path,
) -> List[Path]:
    """
    Save fridge sheets in all languages to files.

    Returns list of saved file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files = []

    # Save English version
    english_path = output_dir / f"fridge_sheet_{fridge_sheet.patient_name.lower()}_english.txt"
    with open(english_path, "w", encoding="utf-8") as f:
        f.write(format_fridge_sheet_text(fridge_sheet, "english"))
    saved_files.append(english_path)

    # Save each translated version
    for lang_name in fridge_sheet.translations.keys():
        lang_path = output_dir / f"fridge_sheet_{fridge_sheet.patient_name.lower()}_{lang_name}.txt"
        with open(lang_path, "w", encoding="utf-8") as f:
            f.write(format_fridge_sheet_text(fridge_sheet, lang_name))
        saved_files.append(lang_path)

    # Save JSON with all data
    json_path = output_dir / f"fridge_sheet_{fridge_sheet.patient_name.lower()}_all.json"

    json_data = {
        "patient_name": fridge_sheet.patient_name,
        "english": fridge_sheet.english_version,
        "translations": {},
        "validation_summary": {
            "all_valid": fridge_sheet.all_valid,
            "valid_languages": fridge_sheet.valid_languages,
            "failed_languages": fridge_sheet.failed_languages,
        },
    }

    for lang_name, translation in fridge_sheet.translations.items():
        json_data["translations"][lang_name] = {
            "language_code": translation.target_lang,
            "language_display": LANGUAGE_NAMES.get(translation.target_lang, lang_name),
            "medications": translation.translated.get("medications", []),
            "is_valid": translation.is_valid,
            "errors": translation.validation_errors,
            "warnings": translation.warnings,
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    saved_files.append(json_path)

    return saved_files


def main():
    """Demo: Generate multilingual fridge sheet from complex patient data."""
    from .llm_client import MedGemmaClient
    from .medication_interpretation import interpret_medication_v3_grounded

    print("\n" + "=" * 60)
    print("MULTILINGUAL FRIDGE SHEET GENERATOR")
    print("=" * 60)

    # Load patient data
    project_root = Path(__file__).parent.parent.parent
    golden_file = project_root / "examples" / "golden_patient_complex.json"

    print(f"\nLoading patient data from: {golden_file}")
    with open(golden_file) as f:
        data = json.load(f)

    patient = data["patient"]
    print(f"Patient: {patient['nickname']} ({patient['age_range']} {patient['sex']})")
    print(f"Medications: {len(data['medications'])}")

    # Process medications with MedGemma
    print(f"\n{'='*60}")
    print("Processing medications with MedGemma V3 (Grounded)...")
    print(f"{'='*60}")

    client = MedGemmaClient()
    medication_results = []

    for i, med in enumerate(tqdm(data["medications"], desc="MedGemma")):
        try:
            result, _ = interpret_medication_v3_grounded(
                client=client,
                medication_name=med["medication_name"],
                sig_text=med["sig_text"],
                clinician_notes=med["clinician_notes"],
                interaction_notes=med["interaction_notes"],
                debug=False,
            )
            result["medication"] = med["medication_name"]
            medication_results.append(result)
        except Exception as e:
            print(f"\nError processing {med['medication_name']}: {e}")
            medication_results.append({
                "medication": med["medication_name"],
                "error": str(e),
            })

    # Generate multilingual fridge sheet
    print(f"\n{'='*60}")
    print("Generating multilingual fridge sheets...")
    print(f"{'='*60}")
    print(f"Target languages: {', '.join(DEFAULT_TARGET_LANGUAGES)}")

    fridge_sheet = generate_multilingual_fridge_sheet(
        patient_name=patient["nickname"],
        medication_results=medication_results,
        target_languages=DEFAULT_TARGET_LANGUAGES,
    )

    # Print validation report
    print_validation_report(fridge_sheet)

    # Print sample outputs
    print(f"\n{'='*60}")
    print("SAMPLE OUTPUT: ENGLISH")
    print(f"{'='*60}")
    print(format_fridge_sheet_text(fridge_sheet, "english"))

    for lang in fridge_sheet.valid_languages[:2]:  # Show first 2 valid translations
        print(f"\n{'='*60}")
        print(f"SAMPLE OUTPUT: {lang.upper()}")
        print(f"{'='*60}")
        print(format_fridge_sheet_text(fridge_sheet, lang))

    # Save outputs
    output_dir = project_root / "outputs" / "multilingual"
    saved_files = save_multilingual_output(fridge_sheet, output_dir)

    print(f"\n{'='*60}")
    print("SAVED FILES")
    print(f"{'='*60}")
    for path in saved_files:
        print(f"  {path}")

    print(f"\nMultilingual fridge sheet generation complete!")


if __name__ == "__main__":
    main()
