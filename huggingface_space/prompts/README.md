# CareMap Prompts

This folder contains the **source-of-truth prompt templates** used by CareMap.
Each prompt is designed to do **one job** and to emit **structured JSON** so the fridge sheet can be rendered as a deterministic table.

## Design intent

CareMap intentionally avoids a “mega prompt” that generates the entire fridge sheet.
Instead, prompts are **task-scoped** to reduce clinical risk, improve consistency, and make behavior testable.

Common principles across all prompts:
- **JSON-only output** (no markdown, no commentary)
- **One item in → one JSON object out**
- **Plain language** (caregiver-friendly)
- **No clinical decision-making** (no diagnosis, no treatment recommendations)
- **Fail closed**: prefer omission or “Not specified — confirm with care team” over guessing

## How these prompts are used

At runtime:
1. EHR-derived data is mapped into a **Canonical JSON** structure.
2. The app calls the relevant prompt(s) to generate safe, plain-language text fields.
3. Outputs are validated (schema + constraints) and assembled into the one-page fridge sheet.

The prompt files are loaded by the notebook/app so judges can review them directly.

---

## `medication_prompt_v1.txt`

**Purpose:** Create one caregiver-safe medication row for the fridge sheet.

**Input fields (provided to the prompt):**
- `medication_name` (normalized)
- `when_to_give` (dose + frequency + timing pulled from the EHR)
- `clinician_notes` (optional)
- `interaction_notes` (optional; verified interactions only)

**Output JSON keys (exact):**
- `medication`
- `why_it_matters` (one sentence; purpose, not mechanism)
- `when_to_give` (must be explicit; if missing → `Not specified — confirm with care team`)
- `important_note` (one sentence max; only if explicitly supported by notes)

**Guardrails:**
- No dosage calculations or changes
- No treatment recommendations
- No speculative interaction warnings (only use provided `interaction_notes`)
- No mechanism-of-action explanations

---

## `lab_prompt_v1.txt`

**Purpose:** Create one high-level lab/test insight item (max 3 total on the fridge sheet).

**Input fields (provided to the prompt):**
- `test_name` (plain name)
- `result_flag` (e.g., Normal / Slightly off / Needs follow-up)
- Optional supporting context from the canonical record (non-numeric)

**Output JSON keys (exact):**
- `what_was_checked` (plain-language description; one short sentence max)
- `what_it_means` (starts with: `Normal` / `Slightly off` / `Needs follow-up`, followed by a brief explanation)
- `what_to_ask_doctor` (exactly one question)

**Guardrails:**
- No raw numeric values
- No reference ranges or thresholds
- No urgency escalation unless explicitly provided by source data
- Uncertainty-aware wording when appropriate (“ask your clinician…”)

---

## `caregap_prompt_v1.txt`

**Purpose:** Explain why a care gap / follow-up task matters, without fear-based language.

**Input fields (provided to the prompt):**
- `care_gap` (the item name)
- `next_step` (the concrete action to take)
- Optional context if explicitly provided by the source record

**Output JSON keys (exact):**
- `care_gap`
- `why_it_matters` (2–3 short sentences; calm, supportive)
- `next_step` (copy the provided next step)

**Guardrails:**
- No diagnosis or outcome prediction
- No fear-based or urgent language unless explicitly provided by source data
- Focus on organization and follow-through, not clinical claims

---

## Versioning

Prompts are versioned with a `_vN` suffix.
When updating a prompt:
- add a new version file (e.g., `_v2`)
- keep older versions for traceability during judging and testing
- update the notebook/app to reference the intended version
