# CareMap Examples

Synthetic patient data and golden test specifications. All patient data is fully synthetic — no real PHI.

---

## Canonical Patient Files (EHR Input)

These follow `CANONICAL_SCHEMA.md v1.1` — structured EHR data fed into the CareMap pipeline.

| File | Description |
|------|-------------|
| `canonical_amma.json` | Primary demo patient — "Amma", 70s, Alzheimer's + Diabetes + Hypertension + Anemia, 10 medications, Bengali-speaking family. Used in HuggingFace Space and Kaggle notebook demos. |
| `canonical_tc01.json` | TC-01 test case — simple diabetic patient |
| `canonical_tc02.json` | TC-02 test case |
| `golden_patient_complex.json` | Complex elderly patient ("Dadu"), 7 comorbidities, 8 medications — used in integration tests |
| `golden_patient_simple.json` | Simple patient for baseline unit testing |
| `sample_patient_01.json` | Alternate demo patient for smoke testing |

---

## Golden Test Specifications (Expected MedGemma Output)

These define **expected behavior** for MedGemma interpretation — used by `tests/integration/` golden tests. Each file contains input content, expected output shape, and forbidden terms that must not appear.

| File | Scenarios | Domain |
|------|-----------|--------|
| `golden_labs.json` | 8 scenarios | Lab interpretation: A1c, eGFR, INR, BNP, CBC, LFTs, TSH, lipids |
| `golden_caregaps.json` | 10 scenarios | Care gap explanations: mammogram, colonoscopy, eye exam, flu shot, etc. |
| `golden_imaging_ct.json` | 5 scenarios | CT report simplification |
| `golden_imaging_mri.json` | 5 scenarios | MRI report simplification |
| `golden_drug_interactions.json` | 7 scenarios | Drug interaction warnings: warfarin, NSAIDs, statins, etc. |

---

## HL7 Sample Messages

| File | Description |
|------|-------------|
| `sample_oru_messages.json` | 20 synthetic HL7 ORU messages used for HL7 triage validation — covers STAT (critical K+, troponin), SOON (elevated INR, worsening renal function), and ROUTINE cases |

---

## Usage

```bash
# Run end-to-end fridge sheet with Amma demo patient
PYTHONPATH=src python -m caremap.assemble_fridge_sheet examples/canonical_amma.json

# Run integration golden tests
PYTHONPATH=src pytest tests/integration/ -v

# Run unit tests (mocked MedGemma, fast)
PYTHONPATH=src pytest tests/ --ignore=tests/integration/
```

See `CANONICAL_SCHEMA.md` for full field definitions.
