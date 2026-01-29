# Changelog

All notable changes to CareMap will be documented in this file.

## [Unreleased]

### Added
- **View mode toggle** in HuggingFace app: Detailed (full AI output) vs Brief (printable)
- **Multilingual support**: Output in 10 languages (English, Spanish, Chinese, Hindi, Arabic, Portuguese, French, German, Japanese, Korean)
- **HuggingFace Spaces app** for interactive demo with Gradio
- **Jupyter notebook** for Kaggle submission
- **Forbidden content sections** in prompts for plain language enforcement

### Changed
- UI improvements with section emojis for better readability

### Fixed
- `require_one_question` validator now enforces exactly one question mark (was allowing multiple)
