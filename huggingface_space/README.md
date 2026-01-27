---
title: CareMap - Caregiver Fridge Sheet
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: apache-2.0
models:
  - google/medgemma-4b-it
---

# CareMap: AI-Powered Caregiver Fridge Sheet

Transform complex patient health data into a simple, one-page caregiver aid that can be printed and stuck on the refrigerator.

## What is CareMap?

Family caregivers receive overwhelming amounts of medical information:
- Dense clinical notes with jargon
- Multiple medication instructions
- Lab results with unexplained abbreviations
- Scattered follow-up tasks

**CareMap** uses MedGemma to convert this into plain-language explanations at a 6th-grade reading level.

## Features

- **Lab Interpretation**: Explains what tests check and what results mean
- **Medication Summaries**: What each medicine does and safety notes
- **Care Gap Actions**: Clear to-do items grouped by urgency
- **One-Page Format**: Designed to fit on a single printable sheet
- **Multilingual Support**: Output in 10 languages (English, Spanish, Chinese, Hindi, Arabic, Portuguese, French, German, Japanese, Korean)
- **View Modes**:
  - 📖 **Detailed**: Full AI explanations with why/how/watch-out notes
  - 📋 **Brief**: Condensed printable summary

## Safety by Design

CareMap is built with safety guardrails:
- No diagnoses or treatment recommendations
- No dosage instructions or changes
- No medical jargon (forbidden term lists)
- Questions for the doctor, not answers

## Model

This app uses **MedGemma 4B-IT** from Google Health AI.

```bibtex
@article{sellergren2025medgemma,
  title={MedGemma Technical Report},
  author={Sellergren, Andrew and others},
  journal={arXiv preprint arXiv:2507.05201},
  year={2025}
}
```

## Usage

1. Paste patient JSON data (see example format in the app)
2. Select output language
3. Choose view mode (Detailed or Brief)
4. Click "Generate Fridge Sheet"
5. Print and post on the refrigerator!

## Links

- [GitHub Repository](https://github.com/YOUR_USERNAME/caremap-medgemma)
- [Kaggle Notebook](https://www.kaggle.com/YOUR_USERNAME/caremap)
- [MedGemma Impact Challenge](https://www.kaggle.com/competitions/medgemma-impact-challenge)

---

*This tool is for informational purposes only and does not provide medical advice.*
