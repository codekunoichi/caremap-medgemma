# Changelog

All notable changes to CareMap will be documented in this file.

## [Unreleased]

### Added
- **Quantitative evaluation tables** in Kaggle notebook: batch evaluation across all 4 modules
  - Radiology triage: 25-image confusion matrix with STAT recall
  - HL7 triage: 20-message confusion matrix with STAT recall
  - Medication interpretation: per-med safety checklist (JSON parse / schema / SafetyValidator)
  - Lab interpretation: per-scenario golden spec check (schema / forbidden terms / question mark)
  - Combined scorecard table and clinical takeaways section
- **Plain-text response parser** for radiology triage (`_parse_text_response`): handles MedGemma 1.5 multimodal responses that return key-value text instead of JSON
- **Kaggle dataset build script** (`build_kaggle_dataset.sh`): zips src, prompts, examples, and NIH demo images with 15MB size guard

### Fixed
- **T4 OOM on multimodal load**: notebook now deletes NLLB translator before loading multimodal client, freeing ~1.2GB GPU memory
- **v1.5 multimodal pipeline**: passes `processor=` (not `tokenizer=`) for MedGemma 1.5, fixing incorrect image preprocessing
- **Kaggle dataset mount path**: auto-detects standard and user-prefixed mount paths with rglob fallback

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
