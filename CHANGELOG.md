# Changelog

All notable changes to CareMap will be documented in this file.

## [Unreleased]

### Added
- **YouTube video demo**: 4-minute competition walkthrough published and linked across README, WRITEUP, and HuggingFace Space README
- **Kaggle notebook public**: `caremap-medgemma-competition-v8` published and linked across all docs
- **Pencil sketch + fridge photo**: Personal images (`MaAndBapi.PNG`, `MaPillBox.png`, `fridgesheet.png`) added to `docs/images/` and embedded in README and HuggingFace Space README
- **Acknowledgements section**: Credits for user research partners, LLM council, and Kaggle/Google added to README and WRITEUP

### Changed
- **README Deployments table**: Kaggle notebook row updated from local path to public URL; Video Demo row added
- **WRITEUP.md**: Kaggle notebook linked; Video Demo link updated from `[link TBD]` to YouTube URL
- **HuggingFace Space README**: Kaggle notebook "Coming Soon" replaced with public URL; YouTube video link added; em-dashes replaced with hyphens; radiology timing updated to match writeup (STAT = intervene now, SOON = < 1 hour, ROUTINE = < 24 hours); Ayah context added
- **NLLB-200 language count**: Updated from numbered list to "600+ languages" across all docs

## [v1.5-medgemma-ready]

### Added
- **Competition writeup** (`WRITEUP.md`): 3-page writeup covering personal motivation, WHO $42B impact stat, three-module architecture, proof-of-architecture evaluation, SaMD regulatory positioning, and NLLB-200 as decoupled translation layer
- **Rule-based priority override for radiology triage** (`priority_rules.py`): physician-auditable CSV maps finding patterns to minimum priority levels; rules only escalate, never downgrade
  - 13 clinical rules (4 STAT, 7 SOON, 2 ROUTINE) in `radiology_priority_rules.csv`
  - "No Finding" / "Normal" / "Unremarkable" forces ROUTINE to fix SOON over-prediction
  - `TriageResult` now tracks `model_priority` and `matched_rules` for diagnostic transparency
  - 20 unit tests covering escalation, case-insensitive matching, and no-finding override
- **Rule override diagnostic cell** in Kaggle notebook: shows which rules fired on each misclassified case with per-rule misclassification counts
- **Design insight markdown cell** in Kaggle notebook: explains the divide-and-conquer architecture (MedGemma for detection, rules for priority) and the evolution from 42% to ~50% accuracy with 100% STAT recall
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
- **User research prototypes** (`user_research/`): HTML concept mockups (A/B/C) used in physician and caregiver interviews, plus interview summary and question set
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
