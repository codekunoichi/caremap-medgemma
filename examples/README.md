# CareMap Examples Directory

This directory contains golden test files for demonstrating and validating MedGemma's plain-language interpretation capabilities.

## File Organization

### Canonical Patient Files (INPUT to MedGemma)
These files follow `CANONICAL_SCHEMA.md v1.1` exactly - they represent structured EHR data that MedGemma will process:

| File | Description |
|------|-------------|
| `canonical_tc01.json` | Original TC-01 test case - simple diabetic patient |
| `canonical_tc02.json` | TC-02 test case |
| `golden_patient_complex.json` | Complex elderly patient (80s, "Dadu") with 7 comorbidities, 8 medications |
| `golden_patient_simple.json` | Simpler patient for baseline testing |

### MedGemma Output Specification Files (Expected OUTPUT)
These files document **expected MedGemma behavior** for specific medical domains. They contain:
- Raw medical content (radiology reports, detailed lab context)
- Expected plain language output at 6th grade reading level
- Forbidden terms that should not appear in output

| File | Description |
|------|-------------|
| `golden_labs.json` | 8 lab result interpretation scenarios (A1c, eGFR, INR, BNP, etc.) |
| `golden_imaging_ct.json` | 5 CT scan report simplification scenarios |
| `golden_imaging_mri.json` | 5 MRI report simplification scenarios |
| `golden_caregaps.json` | 10 care gap explanation scenarios |
| `golden_drug_interactions.json` | 7 drug interaction warning scenarios |

## Why Two Types of Files?

**Canonical patient files** represent structured EHR data (medications list, lab flags, care gaps) that feeds into CareMap's interpretation pipeline.

**Output specification files** test MedGemma's ability to interpret raw medical content that wouldn't normally appear in structured EHR fields - like full radiology report text or detailed lab interpretation context.

## Usage

1. **For end-to-end testing**: Use canonical patient files as input
2. **For module-specific testing**: Use output specification files to validate MedGemma's interpretation of specific content types
3. **For competition demos**: Use `golden_patient_complex.json` to show complex real-world scenarios

## Schema Reference

See `CANONICAL_SCHEMA.md` (v1.1) for the full field definitions.
