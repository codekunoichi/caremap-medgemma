# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CareMap converts complex health data (medications, labs, care gaps, imaging) into a single-page caregiver-friendly "fridge sheet" using Google's MedGemma LLM for plain-language explanations.

**Design Principles:**
- One page, always (hard caps on output size)
- Action over information
- Plain language (6th grade reading level)
- Fail closed (omit rather than speculate)
- No diagnosis, dosage changes, or treatment recommendations

## Commands

```bash
# Always use virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run all unit tests (fast, uses mocked LLM)
PYTHONPATH=src pytest tests/ --ignore=tests/integration/

# Run integration tests (slow, requires real MedGemma model + HuggingFace auth)
PYTHONPATH=src pytest tests/integration/ -v

# Run single test file
PYTHONPATH=src pytest tests/test_lab_interpretation.py -v

# Run single test
PYTHONPATH=src pytest tests/integration/test_golden_labs.py::TestGoldenLabs::test_lab_output_structure[LAB-001] -v

# Run a module directly (e.g., medication interpretation demo)
PYTHONPATH=src python -m caremap.medication_interpretation

# Build Kaggle dataset zip (~10MB, 77 files)
./build_kaggle_dataset.sh
```

## Architecture

### Data Flow

```
Canonical Patient JSON (v1.1 EHR-aligned from examples/)
    ↓
assemble_fridge_sheet.py (orchestrator)
    ├─→ medication_interpretation.py → MedGemma → JSON
    ├─→ lab_interpretation.py → MedGemma → JSON
    ├─→ caregap_interpretation.py → MedGemma → JSON
    └─→ imaging_interpretation.py → MedGemma → JSON
    ↓
Fridge Sheet JSON (capped by BuildLimits: 8 meds, 3 labs, 2 actions/bucket)
    ↓
(optional) translation.py → NLLB-200 → Multilingual output
```

### Key Modules (`src/caremap/`)

| Module | Purpose |
|--------|---------|
| `llm_client.py` | Version-aware MedGemma client (v1 + v1.5), device detection (CUDA/MPS/CPU), text + multimodal support |
| `prompt_loader.py` | Loads templates from `prompts/`, uses `{{VARNAME}}` substitution |
| `*_interpretation.py` | Domain-specific interpreters (meds, labs, caregaps, imaging) |
| `assemble_fridge_sheet.py` | Orchestrates all interpreters, applies BuildLimits |
| `radiology_triage.py` | AI-assisted X-ray prioritization (STAT/SOON/ROUTINE) with multimodal MedGemma |
| `hl7_triage.py` | HL7 ORU message triage with priority classification |
| `fridge_sheet_html.py` | Generates 5 printable HTML pages (8.5x11") from fridge sheet JSON |
| `html_translator.py` | DOM-based HTML translation using lxml, preserves safety-critical elements |
| `validators.py` | JSON extraction, schema validation, `require_keys_with_defaults` for resilient validation |
| `safety_validator.py` | Forbidden terms, jargon detection, negation preservation checks |
| `translation.py` | NLLB-200 translator with back-translation validation |
| `multilingual_fridge_sheet.py` | Generates fridge sheets in multiple languages |

### Alternative: Structured Output (`src/caremap_structured/`)

Uses Pydantic + `outlines` library for guaranteed valid JSON via token-level constraints:
- `schemas/` - Pydantic models for each domain (medication, lab, imaging, caregap)
- `generators/structured_generator.py` - StructuredMedGemmaClient with schema-constrained generation

### HuggingFace Space (`huggingface_space/`)

Gradio web app for interactive demo. Contains copied core modules for standalone deployment. Changes to `src/caremap/` must be manually synced here.

### Kaggle Submission

- **Notebook**: `notebooks/caremap_kaggle_submission.ipynb` (the competition deliverable)
- **Local notebook**: `notebooks/caremap_final_submission.ipynb` (for Mac development)
- **Dataset build**: `./build_kaggle_dataset.sh` → `kaggle_dataset/caremap-medgemma-dataset.zip`
- **Environment**: Python 3.12, T4 GPU (16GB VRAM), `kaggle_secrets` for HF auth
- **GPU budget**: ~29 min for full evaluation (61 MedGemma calls across 4 modules)
- **OOM prevention**: Notebook deletes NLLB translator before loading multimodal client to free ~1.2GB GPU memory

### Prompt Templates (`prompts/`)

Each prompt is task-scoped: one item in → one JSON object out. All enforce:
- No diagnosis or treatment recommendations
- Plain language output
- Specific JSON keys per domain

Versions: V1 (constrained), V2 (experimental), V3 (grounded with chain-of-thought)

### Test Structure

- `tests/test_*.py` - Unit tests with mocked MedGemma client
- `tests/integration/test_golden_*.py` - Real MedGemma calls validated against golden specs
- `tests/helpers/` - Golden validators and scenario loaders
- `examples/golden_*.json` - Golden test specifications with expected outputs and forbidden terms

## MedGemma Integration

The client auto-detects v1 vs v1.5 from the `model_id` string (checks for "1.5"):
- **v1**: `AutoModelForCausalLM` + `AutoTokenizer`
- **v1.5**: `AutoModelForImageTextToText` + `AutoProcessor` (requires `transformers>=4.50.0`)

```python
from caremap import MedGemmaClient

client = MedGemmaClient(
    model_id="google/medgemma-1.5-4b-it",  # Default; gated model - requires HuggingFace auth
    device=None,  # Auto-detects CUDA > MPS > CPU
    enable_multimodal=False  # Set True for image support (radiology triage)
)
```

**Device-specific dtype behavior:**
- CUDA: `bfloat16` (not float16 — float16 causes empty output on MedGemma 1.5)
- MPS (Apple Silicon): `float32` (bfloat16/float16 cause NaN issues)
- CPU: `float32`

**Important notes:**
- `max_new_tokens` defaults to 1024 — v3 grounded prompts (reasoning + JSON) truncate at 512
- Multimodal pipeline passes `model=self.model` (not `model=self.model_id`) to avoid loading a second copy (OOM on T4 16GB)
- v1.5 wraps JSON in markdown fences — `extract_first_json_object` in `validators.py` handles this
- v1.5 may omit JSON keys non-deterministically — `require_keys_with_defaults()` fills missing keys with safe defaults
- LLM outputs are non-deterministic; integration tests may have variable results between runs

## Key Documentation

- `CANONICAL_SCHEMA.md` - v1.1 EHR input schema specification
- `INPUT_OUTPUT_RULES.md` - Deterministic transformation rules
- `FRIDGE_SHEET_SCHEMA.md` - Output schema (locked)
- `SAFETY_AND_LIMITATIONS.md` - Explicit non-goals and safeguards
- `CHANGELOG.md` - All notable changes
- `WRITEUP.md` - Competition writeup

## Git Tags

- `v1.0-medgemma-final` - MedGemma 1.0 baseline
- `v1.5-medgemma-ready` - MedGemma 1.5 migration complete
