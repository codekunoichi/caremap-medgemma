# CareMap: One Model, Three Modules, Maximum Impact

**CareMap** uses a single MedGemma model to serve both sides of healthcare — caregivers who need plain-language medication guides, and providers who need intelligent triage queues.

**Team:** [Rumpa Giri](https://www.linkedin.com/in/rgiri/) (Solo developer) | User research: Dr. Vinodhini Sriram (Family Medicine), Dr. Manini Moudgal (Pediatrician, India), Dr. Gaurav Mishra (Psychiatrist, Geriatric), Sunayana Mann (Family Caregiver)

---

## Problem + Why This Is Personal

**This is personal.** My mother lived in India with Alzheimer's, Diabetes, Hypertension, Hyperlipidemia, and Acute Anemia. She took a plethora of medications with complex timing and interactions. Her primary caregiver was my father — 84 years old. The Ayahs (home health workers) rotated constantly. Every time a new Ayah arrived, my father had to re-explain every medication, every timing, every warning from memory. He was exhausted. Instructions got lost. Critical details — which pill must be taken before food, which blood thinner cannot be combined with painkillers — slipped through the cracks. We lived through this for years until she passed away last year. The pain persists, but so does the conviction that it didn't have to be this hard. I built CareMap in her honor — so that other families have a printed sheet on the fridge that anchors every handoff. Not memory. Not verbal instructions. A checklist that stays when the people rotate.

**This is not just our family's problem.** Medication errors cost [US $42 billion annually worldwide](https://www.who.int/news/item/29-03-2017-who-launches-global-effort-to-halve-medication-related-errors-in-5-years) (WHO, 2017). India has 80+ million family caregivers; doctors see 125-175 patients per day. On the provider side, India has one radiologist per 100,000 patients with 72-hour report delays, and clinical labs generate 1,000+ HL7 messages per day where critical values sit unread behind routine results.

**What users told us:** We interviewed four healthcare professionals and caregivers. Their feedback directly shaped CareMap:

> *"All they need is that first page — medication, 8:00 a.m., 12 p.m., with food. This page is the valuable page."* — **Dr. Vinodhini Sriram**, Family Medicine

> *"I peel the fridge magnet and say these are the medications she has."* — **Sunayana Mann**, Caregiver

> *"Even a basic printed list would be a great help... Keep it one page, very impactful."* — **Dr. Manini Moudgal**, Pediatrician, Bangalore

> *"The ayah changes every week. How do you hand off care?"* — **Dr. Gaurav Mishra**, Psychiatrist

---

## Solution: Three Modules, One Model (MedGemma 1.5 4B-IT)

| Module | Audience | MedGemma Mode | What It Does |
|--------|----------|---------------|--------------|
| **Fridge Sheets** | Caregivers & Ayahs | Text reasoning | 5 printable pages from EHR data |
| **Radiology Triage** | Radiologists | **Multimodal** | Prioritizes X-ray review queue |
| **HL7 Triage** | Lab/Clinical Staff | Text reasoning | Surfaces critical lab values |

**Module 1: Fridge Sheet Generator.** MedGemma transforms clinical jargon into plain language at a validated Flesch-Kincaid grade level of 5.5 (measured via `textstat` across 16 medication explanations). Output: five printable 8.5x11" pages — Medication Schedule (for Ayah), Lab Results, Care Actions, Imaging, and Connections (how meds/labs/actions relate). MedGemma generates "Ask the Doctor" prompts so families know *what questions to ask*. Multilingual translation via NLLB-200 supports Bengali, Hindi, and 8 other languages, preserving medication names as safety-critical untranslated elements.

**Module 2: Radiology Triage (Divide-and-Conquer).** Our key technical insight: MedGemma 1.5 scores **0% STAT recall** when asked to do perception + prioritization together, but **100% STAT recall** when we decouple them. MedGemma detects findings (edema, pneumothorax); a physician-auditable CSV rule engine maps findings to priority — STAT (intervene now), SOON (< 1 hour), ROUTINE (< 24 hours) — validated by Dr. Vinodhini Sriram. Rules only escalate, never downgrade — over-triage is preferred because a false STAT is an inconvenience; a missed STAT is a death.

**Module 3: HL7 Message Triage.** MedGemma triages incoming lab results by urgency, surfacing critical values (Troponin elevation, K+ >6.5) above routine results.

---

## Technical Details + Evaluation

**Architecture:** All modules share a single `MedGemmaClient` (auto-detects v1/v1.5, optimal dtype per device). Prompt templates enforce domain-specific JSON schemas. A `SafetyValidator` blocks forbidden terms, jargon, and raw numeric values on every output. CareMap never diagnoses, never recommends treatment, never displays raw lab values. It fails closed — omitting rather than speculating. Emergency contacts are hardcoded, never model-generated. CareMap is a caregiver support aid, not a SaMD — all outputs require human review.

**Proof-of-Architecture Validation (Kaggle T4 GPU, ~29 min):**

| Module | N | Primary Metric | Score |
|--------|---|----------------|-------|
| Radiology Triage | 26 X-rays | STAT Recall | **100%** (3/3) |
| Radiology Triage | 26 X-rays | Overall Accuracy | 50% (deliberate over-triage) |
| HL7 Triage | 20 ORU messages | Overall Accuracy | **85%** |
| Medication Interp. | 8 medications | Safety Pass Rate | **100%** |
| Lab Interp. | 8 golden scenarios | No Forbidden Terms | **100%** |
| Reading Level | 16 med explanations | Flesch-Kincaid Grade | **5.5** (target: 6.0) |

**Honest limitations:** Radiology overall accuracy is 50% due to deliberate over-triage — the rule engine escalates ambiguous cases. The rule CSV includes a diagnostic view showing which rules fired on each misclassified case, making iterative clinician refinement transparent. LLM outputs are non-deterministic; scores represent a single pass. Sample sizes are small — the contribution is the *framework* (divide-and-conquer, physician-auditable rules, safety-first validation), not benchmark numbers. MedGemma 1.5 sometimes omits JSON keys non-deterministically; `require_keys_with_defaults()` fills missing keys with safe fallback text, ensuring the fridge sheet always renders.

**Deployment:** Kaggle notebook (reproducible end-to-end), [HuggingFace Spaces](https://huggingface.co/spaces/rgiri2025/caremap-medgemma) (interactive demo), and printable HTML — the actual deliverable requires zero technology once printed. CareMap requires structured clinical data as input; in India where paper records dominate, multimodal data extraction from pill strips and PDF reports is a natural next step.

---

## Acknowledgements

**Family.** My father, whose insights shaped the concept. My mother, whose encouragement to keep moving forward lives on in this work.

**User Research Partners.** [Dr. Vinodhini Sriram](https://www.pihhealth.org/find-a-doctor/physician-profile-advanced/vinodhini-sriram/) (Family Medicine), [Dr. Gaurav Mishra](https://www.linkedin.com/in/gaurav-mishra-md-mba-dfapa-99213a5/) (Psychiatrist), Dr. Manini Moudgal (Pediatrician, India), [Sunayana Mann](https://www.linkedin.com/in/sunayana-mann/) (Digital Health & Caregiver).

**LLM Council.** Claude (Anthropic), ChatGPT (OpenAI), Gemini (Google) — thought partners, devil's advocates, and research aids. **Claude Code** — for orchestrating the implementation and making a solo developer brave enough to attempt this competition.

**Kaggle & Google.** For hosting this challenge and the opportunity to learn MedGemma by building with it.

---

**Source Code:** [github.com/codekunoichi/caremap-medgemma](https://github.com/codekunoichi/caremap-medgemma)
**Live Demo:** [HuggingFace Spaces](https://huggingface.co/spaces/rgiri2025/caremap-medgemma)
**Video Demo:** [link TBD]
