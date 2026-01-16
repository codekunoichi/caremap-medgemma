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

# CareMap Canonical Input Schema (v1.1) — EHR-Aligned (CCDA-Friendly)

CareMap aims to be **EHR-friendly** and easy to map from standards like **CCDA** (and optionally FHIR).
To do that, the canonical input schema is designed to look like a **simplified EHR extract**: fields come **as-is** from the chart (names, sig/timing, flags), and CareMap/MedGemma adds caregiver-friendly interpretation downstream.

This canonical schema is the **contract** between:
- ingestion adapters (CCDA / FHIR / portal export)
- deterministic rules (`INPUT_OUTPUT_RULES.md`)
- prompt outputs (`prompts/*.txt`)
- the one-page fridge sheet layout (`FRIDGE_SHEET_SCHEMA.md`)
- golden tests (`TEST_CASES.md`)

For reproducibility, this repo includes sample canonical JSON fixtures that anyone can run locally.

---

## Design Goals

- **Close to CCDA content** so mapping is straightforward
- **Minimal but sufficient** for a one-page caregiver “fridge sheet”
- **PHI-minimized by design** (avoid identifiers when possible)
- **Stable** across vendor variability (handle missing fields)
- **Safe defaults** (fail closed; do not guess missing timing)

---

## Canonical JSON Shape (EHR Extract)

Top-level object:

- `meta` (optional)
- `patient` (optional)
- `problem_list` (optional)
- `medications` (optional)
- `results` (optional)
- `care_gaps` (optional)
- `care_team` (optional)
- `contacts` (optional)

All fields are optional to support partial data and fail-closed behavior.

---

## Field Definitions

### `meta` (object, optional)

| Field | Type | Example | Notes |
|---|---|---|---|
| `source` | string | `"CCDA"` | `"CCDA"`, `"FHIR"`, `"PortalExport"`, `"Manual"` |
| `generated_on` | string | `"2026-01-15"` | ISO date, used as the time anchor for “Today/This Week/Later” |
| `language` | string | `"en"` | Output language preference (used later for translation) |

---

### `patient` (object, optional)

Used only for the **Care Snapshot** section. Keep it **non-identifying**.

| Field | Type | Example | Notes |
|---|---|---|---|
| `nickname` | string | `"Maa"` | Optional; avoid legal names |
| `age_range` | string | `"70s"` | Coarse ranges only |
| `sex` | string | `"F"` | Optional |
| `conditions_display` | array[string] | `["Diabetes", "High blood pressure"]` | Optional; plain language preferred (max 3 for output) |

---

### `problem_list` (array, optional)

Represents an EHR/CCDA **Problems** section.

Each problem item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `display` | string | `"Type 2 diabetes mellitus"` | Human-readable label from EHR/CCDA |
| `status` | string | `"Active"` | Optional |
| `onset_date` | string | `"2016-05-01"` | Optional |

CareMap may map a subset of these into `patient.conditions_display`.

---

### `medications` (array, optional)

Represents an EHR/CCDA **Medications** section. Fields are intentionally close to what is available in CCDA medication entries.

Each medication item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `medication_name` | string | `"Metformin"` | Required if item exists |
| `sig_text` | string | `"Take 1 tablet by mouth twice daily with meals"` | As written in the chart if available |
| `dose` | string | `"500 mg"` | Optional (often derivable from sig) |
| `route` | string | `"PO"` | Optional |
| `frequency` | string | `"BID"` | Optional (EHR shorthand allowed) |
| `timing` | string | `"morning and evening"` | Optional (preferred caregiver-friendly timing if available) |
| `start_date` | string | `"2024-01-10"` | Optional |
| `end_date` | string | `""` | Optional |
| `status` | string | `"Active"` | Optional |
| `clinician_notes` | string | `"Take with food"` | Optional; safety/handling notes only |
| `interaction_notes` | string | `"Do not give with XYZ unless advised by care team"` | Optional; verified interactions only (no speculation) |

**Important v1.1 rule:** If timing/dose/frequency are missing, the downstream fridge sheet must use:
`"Not specified — confirm with care team"`
(no “as prescribed” shortcuts).

---

### `results` (array, optional)

Represents an EHR/CCDA **Results / Labs / Tests** section. In v1.1, we keep it **safe and printable** by avoiding reference ranges in the canonical form unless the source provides them clearly.

Each result item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `test_name` | string | `"Hemoglobin"` | Required if item exists |
| `meaning_category` | string | `"Needs follow-up"` | One of: `Normal`, `Slightly off`, `Needs follow-up` (pre-computed by ingestion logic) |
| `flag` | string | `"low"` | Optional (EHR-style: high/low/abnormal/normal/unknown) |
| `result_date` | string | `"2026-01-05"` | Optional |
| `source_note` | string | `"Flagged low in portal"` | Optional; non-numeric context only |

**Rule:** CareMap does not require numeric values for the fridge sheet. If you ingest values, keep them out of v1.1 canonical fixtures unless you have a clear safety rationale.

---

### `care_gaps` (array, optional)

Represents overdue items / reminders / HEDIS-style gaps commonly visible in EHR “Health Maintenance” or “Care Gaps” views.

Each care gap item:

| Field | Type | Example | Notes |
|---|---|---|---|
| `item_text` | string | `"Eye exam overdue"` | As shown in EHR if possible |
| `next_step` | string | `"Call clinic to schedule"` | Concrete action; verb-first |
| `time_bucket` | string | `"This Week"` | One of: `Today`, `This Week`, `Later` (assigned by rules/ingestion) |
| `source` | string | `"Health Maintenance"` | Optional |

Time buckets are relative and anchored by `meta.generated_on` (rendered on the sheet).

---

### `care_team` (object, optional)

Lightweight representation of care team context. Keep minimal.

| Field | Type | Example | Notes |
|---|---|---|---|
| `primary_clinician` | string | `"Primary Care"` | Optional role label |
| `specialists` | array[string] | `["Endocrinology"]` | Optional |
| `notes` | string | `""` | Optional |

---

### `contacts` (object, optional)

Used for **When to Call for Help** and for pharmacy/clinic details.

| Field | Type | Example | Notes |
|---|---|---|---|
| `clinic_name` | string | `"Riverside Primary Care"` | Optional |
| `clinic_phone` | string | `"555-0100"` | Optional |
| `pharmacy_name` | string | `"Main Street Pharmacy"` | Optional |
| `pharmacy_phone` | string | `"555-0199"` | Optional |
| `pharmacy_address` | string | `"123 Main St, City, ST"` | Optional |

If any contact info is missing, CareMap outputs “Not available”.

---

## Example Canonical Input (TC-01) — EHR-Like

```json
{
  "meta": {
    "source": "CCDA",
    "generated_on": "2026-01-15",
    "language": "en"
  },
  "patient": {
    "nickname": "Maa",
    "age_range": "70s",
    "sex": "F",
    "conditions_display": ["Diabetes", "High blood pressure", "High cholesterol"]
  },
  "medications": [
    {
      "medication_name": "Metformin",
      "sig_text": "Take 1 tablet by mouth twice daily with meals",
      "dose": "500 mg",
      "route": "PO",
      "frequency": "BID",
      "timing": "morning and evening, with food",
      "status": "Active",
      "clinician_notes": "",
      "interaction_notes": ""
    },
    {
      "medication_name": "Atorvastatin",
      "sig_text": "Take 1 tablet by mouth daily at bedtime",
      "dose": "20 mg",
      "route": "PO",
      "frequency": "Daily",
      "timing": "at bedtime",
      "status": "Active",
      "clinician_notes": "",
      "interaction_notes": ""
    }
  ],
  "results": [
    {
      "test_name": "Hemoglobin",
      "meaning_category": "Needs follow-up",
      "flag": "low",
      "result_date": "2026-01-05",
      "source_note": "Flagged low in portal"
    },
    {
      "test_name": "A1c",
      "meaning_category": "Slightly off",
      "flag": "high",
      "result_date": "2026-01-05",
      "source_note": ""
    }
  ],
  "care_gaps": [
    {
      "item_text": "Eye exam overdue",
      "next_step": "Call clinic to schedule",
      "time_bucket": "This Week",
      "source": "Health Maintenance"
    },
    {
      "item_text": "Follow-up visit due",
      "next_step": "Schedule appointment",
      "time_bucket": "Today",
      "source": "After Visit Summary"
    }
  ],
  "contacts": {
    "clinic_name": "Riverside Primary Care",
    "clinic_phone": "555-0100",
    "pharmacy_name": "Main Street Pharmacy",
    "pharmacy_phone": "555-0199",
    "pharmacy_address": "123 Main St, City, ST"
  }
}
```

---

## Mapping Notes (CCDA / FHIR)

### CCDA → canonical (v1.1)
Typical mapping:
- **Medications section** → `medications[]`
  - medication name → `medication_name`
  - instruction/sig text → `sig_text`
  - dose/route/frequency/timing when available → `dose`, `route`, `frequency`, `timing`
  - status/period → `status`, `start_date`, `end_date`
- **Problems section** → `problem_list[]` and/or `patient.conditions_display[]`
- **Results section** → `results[]`
  - test name → `test_name`
  - abnormal flags → `flag`
  - qualitative status for fridge sheet (computed) → `meaning_category`
- **Health Maintenance / Plan / AVS** (vendor-specific) → `care_gaps[]`
- **Header / Participants / ServiceEvent** → `contacts` (vendor variability is high; manual supplement may be needed)

### FHIR → canonical (v1.1)
Typical mapping:
- `MedicationRequest` / `MedicationStatement` → `medications[]`
- `Condition` → `problem_list[]`
- `Observation` → `results[]` (derive `meaning_category` from interpretation flags or high-level rules)
- Care gaps are often not standardized in FHIR; may require EHR-specific endpoints or manual entry.

Adapters are intentionally minimal in v1.1 and prioritize **safe extraction** over completeness.

---

## Versioning

- This schema is **v1.1** and EHR-aligned.
- Future additions must:
  - preserve backwards compatibility where possible
  - not increase PHI risk
  - remain renderable within `FRIDGE_SHEET_SCHEMA.md` (one page)
  - keep MedGemma responsible only for **plain-language explanation**, not clinical decisions