# CareMap Prompts

Task-scoped prompt templates for MedGemma 1.5. Each prompt does **one job** and emits **structured JSON**.

## Design Principles

CareMap avoids a "mega prompt" — prompts are scoped by domain to reduce clinical risk, improve consistency, and make behavior testable.

Common guardrails across all prompts:
- **JSON-only output** — no markdown, no commentary (MedGemma 1.5 may wrap in fences; `extract_first_json_object` handles this)
- **One item in → one JSON object out**
- **Plain language** — 6th-grade reading level
- **No clinical decision-making** — no diagnosis, no treatment recommendations
- **Fail closed** — prefer "Not specified — confirm with care team" over guessing

---

## Fridge Sheet Prompts (Patient Side)

### Medication Prompts
| File | Version | Description |
|------|---------|-------------|
| `medication_prompt_v1.txt` | V1 | Constrained: one medication → plain-language fridge row |
| `medication_prompt_v2_experimental.txt` | V2 | Experimental: broader context, less constrained output |
| `medication_prompt_v3_grounded.txt` | V3 | Grounded: chain-of-thought reasoning before JSON — best quality, requires `max_new_tokens=1024` |

**Output keys:** `medication`, `why_it_matters`, `when_to_give`, `important_note`

### Lab Prompts
| File | Version | Description |
|------|---------|-------------|
| `lab_prompt_v1.txt` | V1 | Constrained: one lab result → plain-language explanation |
| `lab_prompt_v2_experimental.txt` | V2 | Experimental |
| `lab_prompt_v3_grounded.txt` | V3 | Grounded with chain-of-thought |

**Output keys:** `what_was_checked`, `what_it_means`, `what_to_ask_doctor`
**Guardrails:** No raw numeric values, no reference ranges

### Care Gap Prompts
| File | Version | Description |
|------|---------|-------------|
| `caregap_prompt_v1.txt` | V1 | Constrained: one care gap → calm, actionable explanation |
| `caregap_prompt_v2_experimental.txt` | V2 | Experimental |
| `caregap_prompt_v3_grounded.txt` | V3 | Grounded with chain-of-thought |

**Output keys:** `care_gap`, `why_it_matters`, `next_step`
**Guardrails:** No fear-based language, no outcome prediction

### Imaging Prompts
| File | Version | Description |
|------|---------|-------------|
| `imaging_prompt_v1.txt` | V1 | Constrained: one radiology report → plain-language summary |
| `imaging_prompt_v2_experimental.txt` | V2 | Experimental |
| `imaging_prompt_v3_grounded.txt` | V3 | Grounded with chain-of-thought |

**Output keys:** `study_type`, `what_was_found`, `what_it_means`, `what_to_ask_doctor`
**Guardrails:** No diagnosis, no urgency escalation

---

## Provider-Side Prompts

### `radiology_triage.txt`
**Used by:** `radiology_triage.py` (multimodal pipeline)
**Input:** Chest X-ray image + patient age/gender
**Task:** Detect findings and suggest priority — MedGemma's output feeds the rule engine (not used directly for final priority)
**Output keys:** `findings`, `primary_impression`, `suggested_priority`, `confidence`
**Note:** MedGemma alone achieves 0% STAT recall; the CSV rule engine (`radiology_priority_rules.csv`) is what produces 100% STAT recall. This prompt handles perception; rules handle prioritization.

### `hl7_oru_triage.txt`
**Used by:** `hl7_triage.py`
**Input:** HL7 ORU message fields (message type, patient age/gender, clinical context, observations)
**Task:** Classify incoming lab/clinical result as STAT / SOON / ROUTINE
**Output keys:** `priority`, `reasoning`, `key_findings`, `recommended_action`
**Priority definitions:**
- `STAT` — critical values, immediate action (< 1 hour)
- `SOON` — abnormal, same-day review (< 24 hours)
- `ROUTINE` — normal/minor (48–72 hours)

---

## Versioning

Prompts use `_vN` suffix. V3 grounded prompts are the production default — they produce higher quality output via chain-of-thought reasoning but require `max_new_tokens=1024` (truncates at 512). V1 prompts are kept for regression testing.
