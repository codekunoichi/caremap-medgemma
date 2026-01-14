# CareMap Fridge Sheet Schema (v1.0)

This document defines the **locked, one-page output schema** for the CareMap Caregiver Fridge Sheet.

The schema is designed for **caregiving under cognitive load**:
- scannable in 30–60 seconds
- printable on a single page (US Letter or A4)
- usable without phones, portals, or continuous connectivity

CareMap is **not** a medical record. It is an action-oriented caregiver aid.

---

## Output Format

- **Single page only** (no multi-page output)
- Designed for **print** and **shared household visibility**
- Plain language (≈ 6th grade reading level)
- Consistent ordering of sections (below)

---

## Section 1 — Care Snapshot (Orientation Only)

**Purpose:** Help caregivers orient quickly without exposing identifiers.

**Fields**
- **Name / Nickname:** (optional)
- **Age range:** (optional; e.g., “70s”)
- **Key health issues:** max 3, plain-language only

**Rules**
- No DOB, MRN, insurance, address, or provider identifiers
- No clinical codes (ICD/CPT)
- No diagnosis inference if missing

---

## Section 2 — Medications (What / Why / When)

**Purpose:** Reduce medication confusion and prevent common caregiving errors.

**Table columns (fixed)**
| Medication | Why it matters | When to give | Important note |
|---|---|---|---|

**Rules**
- Max **8** medications
- No dosages unless explicitly safe and provided (default: exclude)
- If timing is missing: show **“As prescribed”**
- “Why it matters” must be plain language, one sentence
- “Important note” must be a short safety note (one sentence)
- Only include interaction warnings if **critical** and phrased cautiously

**Examples of acceptable “Important note”**
- “Skip if not eating; confirm with clinician if unsure.”
- “Do not double dose if one is missed.”
- “Check with clinician before mixing with OTC pain meds.”

---

## Section 3 — CareMap Actions (Today / This Week / Later)

**Purpose:** Convert scattered tasks into a prioritized, time-based plan.

**Structure (fixed)**
**Today**
- ☐ Action 1
- ☐ Action 2

**This Week**
- ☐ Action 1
- ☐ Action 2

**Later**
- ☐ Action 1

**Rules**
- Max **2** actions per “Today” and “This Week”; max **1** for “Later”
- Each action must begin with a verb: **Take / Schedule / Call / Ask / Check**
- No informational-only items (must be actionable)
- Relative time only (no absolute dates required)

---

## Section 4 — Things Still Pending (Care Gaps)

**Purpose:** Make overdue or missing care understandable and actionable.

**Structure**
- ☐ [Plain-language item] → **[Next step]**

**Rules**
- No clinical jargon (“care gaps” should not appear on the sheet)
- Max **5** items
- Every item must include a clear next step (Call / Schedule / Ask)

**Example**
- ☐ Eye exam overdue → **Call clinic**

---

## Section 5 — Lab & Test Insights (High-Level Only)

**Purpose:** Provide calm, high-level interpretation without creating clinical risk.

**Structure (per item)**
- **What was checked:** (plain language)
- **What it means:** (Normal / Slightly off / Needs follow-up)
- **What to ask the doctor:** (one question)

**Rules**
- Max **3** items
- No raw numeric values
- No reference ranges
- No urgency escalation unless explicitly provided by source data
- Must include uncertainty-aware wording when appropriate (e.g., “ask your clinician”)

---

## Section 6 — When to Call for Help (Contacts + Escalation)

**Purpose:** Provide immediate, practical contact info and clear escalation guidance.

**Fields**
- **Primary clinic:** name + phone
- **Pharmacy:** name + phone
- **Call urgently if:** fixed list only

**Rules**
- Contacts are copied verbatim from input if present; otherwise “Not available”
- “Call urgently if” uses a **fixed, non-model-generated** list
- No long disclaimers; one clear escalation line

---

## Section 7 — Safety Reminders (Fixed Set)

**Purpose:** Reinforce safe caregiver behavior consistently.

**Fixed bullets**
- Do not stop medications suddenly
- Do not double dose if one is missed
- Ask before mixing medications or supplements

**Rules**
- This section is **static**, not model-generated
- Must always appear on the sheet

---

## Explicitly Excluded (by design)

The Fridge Sheet must not include:
- diagnoses or diagnostic language
- treatment recommendations or changes
- medication dosage calculations or adjustments
- full medical history or problem lists
- insurance details
- provider names beyond clinic contact
- detailed lab values, ranges, or trend charts
- legal or clinical disclaimers that add cognitive load

CareMap prioritizes **clarity, safety, and actionability**.

---

## One-Page Constraint

If inputs exceed capacity:
- Medications: select top 8 by caregiver relevance and safety criticality
- Pending items: select top 5 by urgency and actionability
- Lab insights: select top 3 by abnormality/relevance
- Provide a single line (optional): “For details, refer to the portal or clinician.”

Multi-page output is never allowed.

---
