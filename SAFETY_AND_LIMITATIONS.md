

# Safety and Limitations – CareMap

CareMap is designed as a **caregiver support aid**, not a clinical decision system.  
This document defines the explicit **safety boundaries, limitations, and non-goals** of the project.

These constraints are intentional. They are what make CareMap safer, more trustworthy, and appropriate for real-world caregiving contexts.

---

## Core Safety Principles

1. **Fail Closed, Not Clever**  
   When information is missing, ambiguous, or unsafe to infer, CareMap produces less output rather than guessing.

2. **Action Without Diagnosis**  
   CareMap focuses on *what to do next*, not *what condition someone has*.

3. **Caregiver-First Language**  
   All outputs are written for non-clinicians, prioritizing clarity and calm over clinical precision.

4. **Human-in-the-Loop by Design**  
   CareMap assumes caregivers and clinicians remain responsible for decisions. It does not remove human judgment.

---

## Explicit Non‑Goals

CareMap does **not**:

- diagnose medical conditions
- provide treatment recommendations
- adjust, calculate, or suggest medication dosages
- start, stop, or change medications
- interpret imaging studies
- predict outcomes or risks
- provide emergency or acute care guidance
- replace clinician advice or medical supervision
- function as a complete medical record

If a feature would require any of the above, it is **out of scope by design**.

---

## Medication Safety Boundaries

To reduce risk related to polypharmacy and caregiver error:

- Dosage information is intentionally excluded in v1.0
- Medication timing is displayed only if explicitly provided in input
- Interaction warnings are included **only when critical** and phrased cautiously
- CareMap never suggests medication changes

When uncertainty exists, CareMap defers:
> “Please confirm with the clinician.”

---

## Lab and Test Interpretation Limits

CareMap provides **high-level context only** for labs and tests.

It will:
- describe what a test generally checks
- indicate qualitative status (normal / slightly off / needs follow-up)
- suggest questions to ask a clinician

It will **not**:
- display numeric values or reference ranges
- determine urgency unless explicitly stated in source data
- diagnose or interpret trends
- suggest treatment changes based on results

---

## Emergency Handling

CareMap does not perform emergency triage.

A **fixed, non-model-generated** escalation list is always shown:
- chest pain
- confusion
- fainting

For any emergency, caregivers are instructed to contact emergency services directly.

---

## Privacy and PHI Considerations

CareMap is **PHI-minimized by design**.

- The canonical input schema avoids fields that commonly contain identifiers
- Outputs exclude:
  - dates of birth
  - medical record numbers
  - insurance details
  - full legal names
  - addresses
- Any detected identifiers are removed during normalization

CareMap is designed to support **offline use** (e.g., printed fridge sheet), reducing reliance on persistent digital access.

---

## Model Usage Constraints (MedGemma)

MedGemma is used only for:
- translating medical concepts into plain language
- summarizing medication purpose
- generating high-level lab explanations
- adapting tone and reading level

MedGemma is **not** used for:
- diagnosis
- clinical reasoning
- treatment planning
- medication management

Model output is always constrained by deterministic rules defined in `INPUT_OUTPUT_RULES.md`.

---

## Known Limitations

- Output quality depends on input quality; incomplete data yields limited output
- CCDA and FHIR source data vary significantly by vendor
- Care gaps are not always machine-detectable and may require manual entry
- Cultural and language localization is limited in v1.0
- The one-page constraint may omit lower-priority details

These limitations are accepted trade-offs in favor of safety and usability.

---

## Responsible Use Statement

CareMap is intended to:
- support caregivers
- reduce cognitive overload
- prevent common, avoidable mistakes
- improve clarity and coordination

It is not intended to replace professional medical care.

---

CareMap is built on the belief that **clear boundaries are a form of safety**.