# CareMap (MedGemma)

CareMap turns complex health information into **clear, actionable next steps** for patients and caregivers using **MedGemma**, with digital explainers and a printable, PHI‑minimized **one‑page “fridge sheet”** designed for real‑world caregiving.

This project is part of the **MedGemma Impact Challenge (Kaggle Hackathon)** and is intentionally focused on *applied, human‑centered AI* rather than model tuning or benchmarking.

---

## Why CareMap Exists

Modern healthcare systems generate enormous amounts of data, but caregivers are left to manage:
- multiple medications
- overlapping chronic conditions
- missed follow‑ups and screenings
- fragmented instructions across portals and paper

Under stress, memory fails. Phones die. Portals overwhelm.

CareMap is designed for the moment when a caregiver stands in the kitchen, tired, responsible, and unsure what matters *right now*.

---

## What CareMap Does

CareMap takes health data (labs, medications, care gaps, and instructions) and produces:

### 1. A Caregiver‑Friendly Fridge Sheet (Primary Output)
A single printable page that:
- prioritizes **what to do today, this week, and later**
- explains **why medications matter** in plain language
- highlights **pending care gaps with clear next steps**
- provides **who to call** when help is needed
- avoids unnecessary medical or technical detail

### 2. Digital Explainability (Supporting Output)
Clear, high‑level explanations of labs and care actions written at an accessible reading level, designed to reduce confusion rather than increase anxiety.

---

## What CareMap Is *Not*

CareMap is intentionally constrained.

It does **not**:
- diagnose conditions
- recommend treatment changes
- calculate or adjust medication dosages
- replace clinicians or clinical judgment
- function as a full medical record

CareMap favors **silence over speculation** when information is missing or uncertain.

---

## Who This Is For

- Family caregivers managing complex care
- Patients who want clarity without clinical jargon
- Care teams exploring safer patient communication patterns
- Designers and engineers interested in responsible health AI

CareMap is **caregiver‑first**, not clinician‑first.

---

## Why MedGemma

CareMap uses **MedGemma** to:
- translate medical concepts into plain language
- generate high‑level, uncertainty‑aware explanations
- adapt output to caregiver‑appropriate reading levels

MedGemma is used where medical grounding matters and avoided where deterministic rules are safer.

---

## Design Principles

- One page, always
- Action > information
- Plain language over precision
- Cognitive load awareness
- Safety through constraint
- Offline‑friendly by design

---

## Project Status

Current focus:
- Finalizing the one‑page fridge sheet schema
- Defining strict input → output rules
- Establishing golden test cases

Future work (out of scope for initial submission):
- Agentic workflows
- Interactive caregiver tools
- Localization and multilingual support

---

## Repository Guide

- `INTENT.md` – project purpose and ethical grounding
- `FRIDGE_SHEET_SCHEMA.md` – locked one‑page caregiver schema
- `INPUT_OUTPUT_RULES.md` – deterministic transformation rules
- `SAFETY_AND_LIMITATIONS.md` – explicit non‑goals and safeguards
- `TEST_CASES.md` – golden test cases and quality gates
- `ROADMAP.md` – scoped future directions

---

## License

This project is released under the **Apache License 2.0**.

---

CareMap is built with the belief that **clarity is care**.
