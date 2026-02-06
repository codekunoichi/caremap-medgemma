# Changelog

All notable changes to CareMap will be documented in this file.

## [Unreleased]

### Added
- **HTML fridge sheet translator** (`html_translator.py`): DOM-based translation for Bengali and other languages
  - Preserves safety-critical elements (medication names, doses, MedGemma badges)
  - Injects language-specific fonts for non-Latin scripts (Bengali, Hindi, Tamil, Telugu, etc.)
  - Sets HTML `lang` attribute for accessibility
- **Bengali translation demo** in notebook (Section 1.8): Translates medication and care gap pages with progress bars
- **Language dropdown** in HuggingFace app: Translate fridge sheets to Bengali, Hindi, Spanish, and more
- **Physician feedback demo** (`fake_demo/`): 7 HTML pages comparing one-page vs multi-page fridge sheet concepts for user research
- **View mode toggle** in HuggingFace app: Detailed (full AI output) vs Brief (printable)
- **Multilingual support**: Output in 10 languages (English, Spanish, Chinese, Hindi, Arabic, Portuguese, French, German, Japanese, Korean)
- **HuggingFace Spaces app** for interactive demo with Gradio
- **Jupyter notebook** for Kaggle submission
- **Forbidden content sections** in prompts for plain language enforcement

### Changed
- **User Research section** enhanced with themed categories and MedGemma alignment callouts
- **Impact Summary** now includes "Poster Effect: From Recall to Reference" section
- UI improvements with section emojis for better readability

### Fixed
- `require_one_question` validator now enforces exactly one question mark (was allowing multiple)
