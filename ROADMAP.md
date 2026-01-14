

# CareMap Roadmap

This roadmap outlines the **intentional, staged evolution** of CareMap.

CareMap is designed to **start small, ship safely, and grow deliberately**.  
Each phase is scoped to avoid feature bloat while preserving a clear path toward greater impact.

---

## Guiding Principles for the Roadmap

- Safety and clarity come before feature depth
- Every new capability must justify its presence under caregiver cognitive load
- Backwards compatibility with the canonical schema is preferred
- Agentic workflows are introduced only after the core experience is stable

---

## Phase 1 — Caregiver Fridge Sheet (Current Scope)

**Status:** In progress  
**Primary goal:** Produce a safe, one-page caregiver aid from structured input

### Deliverables
- Canonical input schema (JSON)
- Deterministic input → output rules
- One-page Caregiver Fridge Sheet (printable)
- Golden test cases enforcing safety and constraints
- Minimal demo using canonical JSON fixtures

### Key Characteristics
- Single-page output only
- Plain-language explanations
- No diagnosis, dosage, or treatment changes
- Fail-closed behavior for missing data
- CCDA / FHIR treated as upstream adapters, not dependencies

### Explicitly Out of Scope
- Agent orchestration
- Real-time EHR integrations
- Mobile applications
- Continuous monitoring or alerts
- Billing, coding, or utilization logic

---

## Phase 2 — Digital Explainability Layer

**Status:** Future (post-hackathon)  
**Primary goal:** Improve understanding without increasing risk

### Potential Enhancements
- Expand digital explanations alongside the fridge sheet
- Adjustable reading levels for patient vs caregiver
- Multilingual output (starting with high-priority languages)
- Inline clarification prompts (“What does this mean?”)

### Guardrails
- No expansion of medical decision-making
- One-page constraint preserved for printable output
- All enhancements must degrade gracefully to offline use

---

## Phase 3 — Agentic Care Navigation (Optional / Advanced)

**Status:** Conceptual  
**Primary goal:** Coordinate complex workflows without removing human control

### Possible Agent Roles
- Intake & normalization agent
- Care gap reasoning agent
- Plain-language translation agent
- Safety and contradiction-checking agent

### Constraints
- Agents orchestrate **tasks**, not decisions
- All agent outputs remain auditable and inspectable
- Deterministic safety rules remain authoritative
- Human-in-the-loop remains mandatory

Agentic workflows are **explicitly deferred** until CareMap v1 demonstrates stability and trustworthiness.

---

## Phase 4 — Ingestion Adapters and Interoperability

**Status:** Incremental  
**Primary goal:** Improve compatibility with real-world data sources

### Planned Adapters
- CCDA (priority)
- FHIR (secondary)
- Manual caregiver entry (always supported)
- PDF (best-effort, text-based only)

### Non-Goals
- Deep vendor-specific EHR integrations
- Real-time clinical system coupling
- Proprietary data pipelines

Adapters must map cleanly into the canonical schema without expanding it unnecessarily.

---

## Phase 5 — Evaluation and Real-World Feedback

**Status:** Exploratory  
**Primary goal:** Measure usefulness and reduce harm

### Evaluation Methods
- Caregiver usability feedback
- Task completion clarity (missed meds, missed follow-ups)
- Qualitative feedback from clinicians and care teams

CareMap prioritizes **learning from real use** over theoretical optimization.

---

## Long-Term Vision (Without Commitment)

CareMap may evolve into:
- A reference design for caregiver-safe AI outputs
- An open pattern for PHI-minimized care summaries
- A building block within larger care coordination systems

Any long-term direction must continue to honor CareMap’s core values:
- restraint
- clarity
- safety
- respect for caregivers

---

CareMap’s roadmap reflects a belief that **responsible progress is incremental by design**.