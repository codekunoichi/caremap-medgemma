---
title: CareMap - EHR Enhancement Platform
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.5.1
app_file: app.py
pinned: false
license: apache-2.0
models:
  - google/medgemma-1.5-4b-it
---

# 🏥 CareMap: EHR Enhancement Platform

**One Model. Three Modules. Better Outcomes.**

CareMap enhances existing Electronic Health Records with clinical AI — it doesn't replace your system, it makes it smarter. Powered by Google's **MedGemma 1.5 4B-IT** foundation model.

## The Problem

Healthcare systems generate overwhelming amounts of data that's hard to act on:
- **Caregivers** receive dense clinical notes, unexplained lab values, and scattered follow-up tasks
- **Radiologists** face 72-hour report delays with a 1:100,000 radiologist-to-patient ratio (India)
- **Clinical staff** process 1,000+ HL7 messages per day with no intelligent prioritization

## Three Modules

| Module | Audience | MedGemma Mode | What It Does |
|--------|----------|---------------|--------------|
| **Patient Portal** | Caregivers & Families | Text reasoning | Converts complex EHR data into printable fridge sheets |
| **Radiology Triage** | Radiologists | Multimodal (image + text) | Prioritizes X-ray review queues by clinical urgency |
| **HL7 Message Triage** | Lab/Clinical Staff | Text reasoning | Triages incoming lab results and clinical messages |

### 👨‍👩‍👧 Patient Portal — Printable Fridge Sheets

Transforms patient health data into **5 printable 8.5×11" pages**, each designed for a specific audience:

| Page | For | Content |
|------|-----|---------|
| 📋 Patient Data | Judges/Devs | Raw EHR input — what MedGemma receives |
| 💊 Medications | Ayah/Helper | Daily schedule with timing & food instructions |
| 🔬 Labs | Family | Test results explained in plain language |
| ✅ Care Actions | Family | Tasks organized: Today / This Week / Coming Up |
| 🫁 Imaging | Family | X-ray findings with AI interpretation |
| 🔗 Connections | Both | How meds, labs, and actions work together |

**Multilingual support:** Medication Schedule and Care Actions pages can be translated into 10 languages using NLLB-200 (Spanish, Hindi, Bengali, Chinese, Portuguese, Tamil, Telugu, Marathi).

### 🔬 Radiology Triage — AI-Assisted X-ray Prioritization

MedGemma's multimodal capability analyzes chest X-rays and assigns priority levels:
- 🔴 **STAT** — Critical findings, review within 1 hour
- 🟡 **SOON** — Abnormal findings, same-day review
- 🟢 **ROUTINE** — Normal/minor findings, 48–72 hours

### 📋 HL7 Message Triage — Lab Result Prioritization

Analyzes incoming HL7 ORU messages (labs, radiology reports) and prioritizes the clinical review queue:
- Detects critical values (K⁺ >6.5, elevated troponin, tension pneumothorax)
- Flags abnormal results needing same-day attention (supratherapeutic INR)
- Routes normal results for routine review

## Safety by Design

CareMap is built with safety guardrails:
- No diagnoses or treatment recommendations
- No dosage instructions or changes
- No medical jargon (forbidden term lists enforced)
- Plain language at a 6th-grade reading level
- Questions for the doctor, not answers
- AI-assisted triage for prioritization only — clinicians review ALL results

## Model

This app uses **MedGemma 1.5 4B-IT** from Google Health AI in both text and multimodal modes.

```bibtex
@article{sellergren2025medgemma,
  title={MedGemma Technical Report},
  author={Sellergren, Andrew and others},
  journal={arXiv preprint arXiv:2507.05201},
  year={2025}
}
```

## Links

- [GitHub Repository](https://github.com/codekunoichi/caremap-medgemma)
- Kaggle Notebook — Coming Soon
- [MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge)

---

*This tool is for informational purposes only and does not provide medical advice. AI-assisted triage is for prioritization only — all results must be reviewed by a clinician.*
