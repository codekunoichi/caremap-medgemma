#!/usr/bin/env python3
"""
Hello World: NLLB-200 Translation for CareMap

Demonstrates Meta's NLLB-200 model for translating caregiver-friendly
medical text into multiple languages.

Supported languages for CareMap (subset of NLLB-200's 200 languages):
- Bengali (ben_Beng) - For caregivers in India/Bangladesh
- Spanish (spa_Latn) - For Hispanic caregivers in US/Latin America
- Traditional Chinese (zho_Hant) - For caregivers in Taiwan/Hong Kong
- Hindi (hin_Deva) - For caregivers in India
- Simplified Chinese (zho_Hans) - For caregivers in mainland China

Usage:
    python src/hello_world_translation.py --text "Take one tablet daily" --target ben_Beng
    python src/hello_world_translation.py --text "Take one tablet daily" --target spa_Latn
    python src/hello_world_translation.py --demo

Model: facebook/nllb-200-distilled-600M (smaller, faster)
       facebook/nllb-200-3.3B (higher quality, more memory)

References:
- NLLB-200 Paper: https://arxiv.org/abs/2207.04672
- HuggingFace: https://huggingface.co/facebook/nllb-200-distilled-600M
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


# NLLB-200 language codes for CareMap target languages
SUPPORTED_LANGUAGES = {
    "bengali": "ben_Beng",
    "spanish": "spa_Latn",
    "chinese_traditional": "zho_Hant",
    "chinese_simplified": "zho_Hans",
    "hindi": "hin_Deva",
    "english": "eng_Latn",
    "french": "fra_Latn",
    "arabic": "arb_Arab",
    "portuguese": "por_Latn",
    "russian": "rus_Cyrl",
}

# Human-readable names
LANGUAGE_NAMES = {
    "ben_Beng": "Bengali",
    "spa_Latn": "Spanish",
    "zho_Hant": "Traditional Chinese",
    "zho_Hans": "Simplified Chinese",
    "hin_Deva": "Hindi",
    "eng_Latn": "English",
    "fra_Latn": "French",
    "arb_Arab": "Arabic",
    "por_Latn": "Portuguese",
    "rus_Cyrl": "Russian",
}


def pick_device() -> torch.device:
    """Pick best available device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class NLLBTranslator:
    """
    NLLB-200 translator for CareMap multilingual support.

    Uses Meta's No Language Left Behind model to translate
    caregiver-friendly medical text into 200+ languages.
    """

    def __init__(
        self,
        model_id: str = "facebook/nllb-200-distilled-600M",
        device: Optional[str] = None,
        source_lang: str = "eng_Latn",
    ) -> None:
        """
        Initialize the NLLB translator.

        Args:
            model_id: HuggingFace model ID
                - "facebook/nllb-200-distilled-600M" (1.3GB, faster)
                - "facebook/nllb-200-3.3B" (13GB, higher quality)
            device: Device to use (cuda, mps, cpu, or None for auto)
            source_lang: Source language code (default: English)
        """
        self.model_id = model_id
        self.device = torch.device(device) if device else pick_device()
        self.source_lang = source_lang

        print(f"Loading NLLB model: {model_id}")
        print(f"Device: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            src_lang=source_lang,
        )

        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            model_id,
            dtype=torch.float16 if self.device.type != "cpu" else torch.float32,
        ).to(self.device)

        self.model.eval()
        print("Model loaded successfully!\n")

    def translate(
        self,
        text: str,
        target_lang: str,
        max_length: int = 256,
    ) -> str:
        """
        Translate text to target language.

        Args:
            text: Text to translate (English by default)
            target_lang: Target language code (e.g., "ben_Beng", "spa_Latn")
            max_length: Maximum output length in tokens

        Returns:
            Translated text
        """
        # Tokenize with source language
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        ).to(self.device)

        # Generate translation
        with torch.no_grad():
            generated = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(target_lang),
                max_length=max_length,
                num_beams=5,
                early_stopping=True,
            )

        # Decode
        translated = self.tokenizer.decode(
            generated[0],
            skip_special_tokens=True,
        )

        return translated

    def translate_fridge_sheet_section(
        self,
        section_text: str,
        target_lang: str,
    ) -> str:
        """
        Translate a section of the fridge sheet.

        Preserves formatting by translating line-by-line for structured content.

        Args:
            section_text: Multi-line section text
            target_lang: Target language code

        Returns:
            Translated section with preserved structure
        """
        lines = section_text.strip().split("\n")
        translated_lines = []

        for line in lines:
            # Preserve empty lines and markdown formatting
            if not line.strip() or line.strip().startswith("#") or line.strip().startswith("---"):
                translated_lines.append(line)
            elif line.strip().startswith("- **") or line.strip().startswith("**"):
                # Translate content but preserve markdown
                translated_lines.append(self.translate(line, target_lang))
            else:
                translated_lines.append(self.translate(line, target_lang))

        return "\n".join(translated_lines)


def run_demo(translator: NLLBTranslator) -> None:
    """Run demonstration of translation capabilities."""

    # Sample CareMap fridge sheet content
    demo_texts = [
        # Medication explanations
        "Take one tablet by mouth twice daily with food.",
        "This medicine helps control blood sugar levels.",
        "Do not skip doses. Take at the same time each day.",

        # Care gap actions
        "Schedule an eye exam this week.",
        "Blood tests are due today. Call the clinic.",

        # Lab explanations
        "The blood sugar test shows it needs follow-up.",
        "Please ask your doctor about these results.",

        # Safety note
        "This sheet is for information only. Always confirm with your doctor.",
    ]

    # Target languages for demo
    target_languages = ["ben_Beng", "spa_Latn", "zho_Hant", "hin_Deva"]

    print("=" * 70)
    print("CareMap Translation Demo - NLLB-200")
    print("=" * 70)

    for target_lang in target_languages:
        lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        print(f"\n{'─' * 70}")
        print(f"Translating to: {lang_name} ({target_lang})")
        print("─" * 70)

        for text in demo_texts[:3]:  # Translate first 3 for brevity
            translated = translator.translate(text, target_lang)
            print(f"\nEnglish:  {text}")
            print(f"{lang_name}: {translated}")

    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


def run_fridge_sheet_demo(translator: NLLBTranslator, target_lang: str) -> None:
    """Translate a sample fridge sheet section."""

    sample_section = """## Today's Priorities

- **Blood tests due** → Schedule lab visit
- **Eye exam overdue** → Call clinic to schedule

## Medications

- **Metformin** (Morning and evening, with food)
  - Why it matters: Helps control blood sugar levels.

- **Lisinopril** (Daily)
  - Why it matters: Helps protect kidneys and control blood pressure.

## Safety Note

This sheet is for information only. Always confirm decisions with your doctor.
If you have chest pain, confusion, or fainting, call emergency services."""

    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)

    print("=" * 70)
    print(f"Fridge Sheet Translation Demo → {lang_name}")
    print("=" * 70)

    print("\n--- Original (English) ---\n")
    print(sample_section)

    print(f"\n--- Translated ({lang_name}) ---\n")
    translated = translator.translate_fridge_sheet_section(sample_section, target_lang)
    print(translated)

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="NLLB-200 Translation Demo for CareMap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate a single phrase to Bengali
  python src/hello_world_translation.py --text "Take one tablet daily" --target ben_Beng

  # Translate to Spanish
  python src/hello_world_translation.py --text "Schedule an eye exam" --target spa_Latn

  # Run full demo with multiple languages
  python src/hello_world_translation.py --demo

  # Translate sample fridge sheet to Bengali
  python src/hello_world_translation.py --fridge-demo --target ben_Beng

Supported language codes:
  Bengali:              ben_Beng
  Spanish:              spa_Latn
  Traditional Chinese:  zho_Hant
  Simplified Chinese:   zho_Hans
  Hindi:                hin_Deva
  French:               fra_Latn
  Arabic:               arb_Arab
  Portuguese:           por_Latn
  Russian:              rus_Cyrl
        """,
    )

    parser.add_argument(
        "--text",
        type=str,
        help="Text to translate",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="ben_Beng",
        help="Target language code (default: ben_Beng for Bengali)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="facebook/nllb-200-distilled-600M",
        help="NLLB model ID (default: distilled-600M)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run multi-language demo",
    )
    parser.add_argument(
        "--fridge-demo",
        action="store_true",
        help="Translate sample fridge sheet section",
    )
    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="List supported language codes",
    )

    args = parser.parse_args()

    # List languages and exit
    if args.list_languages:
        print("Supported Languages for CareMap:\n")
        print(f"{'Language':<25} {'Code':<15}")
        print("-" * 40)
        for name, code in sorted(SUPPORTED_LANGUAGES.items()):
            print(f"{name:<25} {code:<15}")
        return

    # Validate target language
    if args.target not in LANGUAGE_NAMES and args.target not in SUPPORTED_LANGUAGES.values():
        print(f"Warning: '{args.target}' may not be a valid NLLB language code.")
        print("Run with --list-languages to see supported codes.\n")

    # Initialize translator
    print("\n" + "=" * 70)
    print("Initializing NLLB-200 Translator")
    print("=" * 70 + "\n")

    translator = NLLBTranslator(model_id=args.model)

    # Run appropriate mode
    if args.demo:
        run_demo(translator)
    elif args.fridge_demo:
        run_fridge_sheet_demo(translator, args.target)
    elif args.text:
        lang_name = LANGUAGE_NAMES.get(args.target, args.target)
        translated = translator.translate(args.text, args.target)
        print(f"Source (English): {args.text}")
        print(f"Target ({lang_name}): {translated}")
    else:
        # Default: translate a sample
        sample = "Take one tablet by mouth twice daily with food."
        lang_name = LANGUAGE_NAMES.get(args.target, args.target)
        translated = translator.translate(sample, args.target)

        print("No --text provided. Translating sample:\n")
        print(f"Source (English): {sample}")
        print(f"Target ({lang_name}): {translated}")
        print("\nUse --help for more options.")


if __name__ == "__main__":
    main()
