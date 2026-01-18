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
pytest tests/ --ignore=tests/integration/

# Run integration tests (slow, requires real MedGemma model + HuggingFace auth)
pytest tests/integration/ -v

# Run single test file
pytest tests/test_lab_interpretation.py -v

# Run single test
pytest tests/integration/test_golden_labs.py::TestGoldenLabs::test_lab_output_structure[LAB-001] -v
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
```

### Key Modules (`src/caremap/`)

| Module | Purpose |
|--------|---------|
| `llm_client.py` | MedGemma client with device detection (CUDA/MPS/CPU), dtype selection, text + multimodal support |
| `prompt_loader.py` | Loads templates from `prompts/`, uses `{{VARNAME}}` substitution |
| `*_interpretation.py` | Domain-specific interpreters (meds, labs, caregaps, imaging) |
| `assemble_fridge_sheet.py` | Orchestrates all interpreters, applies BuildLimits |
| `validators.py` | JSON extraction, schema validation, constraint checking |

### Prompt Templates (`prompts/`)

Each prompt is task-scoped: one item in → one JSON object out. All enforce:
- No diagnosis or treatment recommendations
- Plain language output
- Specific JSON keys per domain

### Test Structure

- `tests/test_*.py` - Unit tests with mocked MedGemma client
- `tests/integration/test_golden_*.py` - Real MedGemma calls validated against golden specs
- `tests/helpers/` - Golden validators and scenario loaders
- `examples/golden_*.json` - Golden test specifications with expected outputs and forbidden terms

## MedGemma Integration

```python
from caremap import MedGemmaClient

client = MedGemmaClient(
    model_id="google/medgemma-4b-it",  # Gated model - requires HuggingFace auth
    device=None,  # Auto-detects CUDA > MPS > CPU
    enable_multimodal=False  # Set True for image support
)
```

**Device-specific behavior:**
- CUDA: float16 for speed
- MPS (Apple Silicon): float32 + greedy decoding for numerical stability
- CPU: float32

**Note:** LLM outputs are non-deterministic. Integration tests may have variable results between runs.

## Key Documentation

- `CANONICAL_SCHEMA.md` - v1.1 EHR input schema specification
- `INPUT_OUTPUT_RULES.md` - Deterministic transformation rules
- `FRIDGE_SHEET_SCHEMA.md` - Output schema (locked)
- `SAFETY_AND_LIMITATIONS.md` - Explicit non-goals and safeguards
