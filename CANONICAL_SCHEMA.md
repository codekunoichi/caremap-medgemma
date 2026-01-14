# CareMap Canonical Input Schema (v1.0)

CareMap supports multiple ingestion sources (CCDA, FHIR, caregiver-entered data). To keep the project **EHR-friendly and testable**, all sources map into a single **canonical JSON structure**.

This canonical schema is the **contract** between:
- ingestion adapters (CCDA/FHIR/PDF/manual entry)
- CareMap’s deterministic rules (`INPUT_OUTPUT_RULES.md`)
- the one-page output (`FRIDGE_SHEET_SCHEMA.md`)
- the golden tests (`TEST_CASES.md`)

For reproducibility, this repo includes sample canonical JSON fixtures that anyone can run locally.

---

## Design Goals

- **Minimal but sufficient** for the one-page fridge sheet
- **PHI-minimized by design** (avoid fields that commonly contain identifiers)
- **Stable** across CCDA/FHIR vendor variability
- **Easy to validate** and unit test

---

## Canonical JSON Shape

Top-level object:

- `patient` (optional)
- `medications` (optional)
- `labs` (optional)
- `pending` (optional)
- `contacts` (optional)

All fields are optional to support partial data and fail-closed behavior.

---

## Field Definitions

### `patient` (object, optional)

Used for the **Care Snapshot** section.

| Field | Type | Example | Notes |
|---|---|---|---|
| `nickname` | string | `"Maa"` | Optional. Avoid full legal names. |
| `age_range` | string | `"70s"` | Optional. Use coarse ranges only. |
| `conditions` | array[string] | `["Diabetes", "High blood pressure"]` | Max 3 in output. Prefer plain language. |

---

### `medications` (array, optional)

Used for the **Medications** section.

Each medication item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `name` | string | `"Metformin"` | Required if item exists. |
| `timing` | string | `"Morning and evening, with food"` | Optional. If missing → “As prescribed”. |
| `notes` | string | `"Skip if not eating"` | Optional. Short, caregiver-safe notes only. |

**Important:** Do not include dosage fields in v1.0. CareMap avoids dosage to reduce risk.

---

### `labs` (array, optional)

Used for the **Lab & Test Insights** section.

Each lab item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `name` | string | `"A1c"` | Required if item exists. |
| `flag` | string | `"high"` | Allowed: `high`, `low`, `normal`, `unknown`. |
| `note` | string | `"Marked abnormal in portal"` | Optional. No numeric values. |

**Rule:** Raw values and reference ranges are intentionally excluded from the canonical schema.

---

### `pending` (array, optional)

Used for **Things Still Pending** and for prioritizing actions.

Each pending item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `item` | string | `"Eye exam overdue"` | Plain language preferred. |
| `next_step` | string | `"Call clinic"` | Verb-first. Allowed verbs: Call / Schedule / Ask / Check. |

---

### `contacts` (object, optional)

Used for **When to Call for Help**.

| Field | Type | Example | Notes |
|---|---|---|---|
| `clinic.name` | string | `"Riverside Primary Care"` | Optional. |
| `clinic.phone` | string | `"555-0100"` | Optional. |
| `pharmacy.name` | string | `"Main Street Pharmacy"` | Optional. |
| `pharmacy.phone` | string | `"555-0199"` | Optional. |

If any contact info is missing, CareMap outputs “Not available”.

---

## Example Canonical Input (TC-01)

```json
{
  "patient": {
    "nickname": "Maa",
    "age_range": "70s",
    "conditions": ["Diabetes", "High blood pressure", "Kidney issues"]
  },
  "medications": [
    { "name": "Metformin", "timing": "Morning and evening, with food", "notes": "" },
    { "name": "Insulin glargine", "timing": "Nightly", "notes": "" },
    { "name": "Lisinopril", "timing": "", "notes": "" },
    { "name": "Furosemide", "timing": "Morning", "notes": "" },
    { "name": "Atorvastatin", "timing": "Nightly", "notes": "" },
    { "name": "Aspirin", "timing": "", "notes": "" },
    { "name": "Levothyroxine", "timing": "Morning", "notes": "" },
    { "name": "Omeprazole", "timing": "", "notes": "" }
  ],
  "labs": [
    { "name": "A1c", "flag": "high", "note": "" }
  ],
  "pending": [
    { "item": "Eye exam overdue", "next_step": "Call clinic" },
    { "item": "A1c lab due", "next_step": "Schedule lab" },
    { "item": "Follow-up appointment", "next_step": "Call clinic" }
  ],
  "contacts": {
    "clinic": { "name": "Riverside Primary Care", "phone": "555-0100" },
    "pharmacy": { "name": "Main Street Pharmacy", "phone": "555-0199" }
  }
}
```

---

## Mapping Notes (CCDA / FHIR)

CareMap’s ingestion adapters convert source data into the canonical structure:

- **CCDA → canonical**
  - Medications section → `medications[]`
  - Problems section → `patient.conditions[]`
  - Results section → `labs[]` (qualitative flags only if available)
  - Contact sections vary by vendor; may be supplemented via manual entry

- **FHIR → canonical**
  - `MedicationRequest` / `MedicationStatement` → `medications[]`
  - `Condition` → `patient.conditions[]`
  - `Observation` → `labs[]` (qualitative flags only)
  - Contacts often require `Organization` / `PractitionerRole`; may be supplemented manually

Adapters are intentionally minimal in v1.0 and prioritize **safe extraction** over completeness.

---

## Versioning

- This schema is **v1.0** and intentionally minimal.
- Any future additions must:
  - preserve backwards compatibility where possible
  - not increase PHI risk
  - not violate `FRIDGE_SHEET_SCHEMA.md` constraints

---
