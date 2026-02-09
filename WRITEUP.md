# CareMap: One Model, Three Modules, Maximum Impact on Both Sides of Healthcare

### Project Name

**CareMap** — an EHR companion that uses MedGemma to serve both patients and providers.

### Your Team

| Name | Specialty | Role |
|------|-----------|------|
| Ruma Giri | Software Engineer, ML/AI | Solo developer — architecture, MedGemma integration, evaluation, deployment |

User research contributors: Dr. Vinodhini Sriram (Primary Care Physician, US), Dr. Manini Moudgal (Pediatrician, Bangalore), Dr. Gaurav Mishra (Psychiatrist, Geriatric Focus), Sunayana Mann (Family Caregiver).

---

### Problem Statement

**The problem is information overload on both sides of healthcare — and it is killing people.**

**This is personal.** My mother lived in India with Alzheimer's, Hyperlipidemia, Acute Anemia, Diabetes, and Hypertension. She took a plethora of medications with complex timing and interactions. Her primary caregiver was my father — 84 years old. The Ayahs (home health workers) rotated constantly. Every time a new Ayah arrived, my father had to re-explain every medication, every timing, every warning from memory. He was exhausted. Instructions got lost. Critical details — which pill must be taken before food, which blood thinner cannot be combined with painkillers — slipped through the cracks. We lived through this for years until she passed away last year. The pain persists, but so does the conviction that it didn't have to be this hard. I built CareMap in her honor — so that other families going through something similar have a printed sheet on the fridge that anchors every handoff. Not memory. Not verbal instructions. A checklist that stays when the people rotate.

**This is not just our family's problem.** Medication errors cost an estimated [US $42 billion annually](https://www.who.int/news/item/29-03-2017-who-launches-global-effort-to-halve-medication-related-errors-in-5-years) worldwide and injure 1.3 million people per year in the US alone, with low- and middle-income countries losing twice as many years of healthy life from the same error rates (WHO Global Patient Safety Challenge, 2017). In India, doctors see 125-175 patients per day. Families carry paper records in bags. There is no EHR infrastructure to speak of. Our user research with four healthcare professionals and caregivers surfaced the same pattern: *"I don't need more information. I need to know what to do next."* Multilingual translation via NLLB-200 after MedGemma interpretation brings the fridge sheet down to the reading level of local Ayahs — in Bengali, Hindi, or any of 10 supported languages — because plain English is still a barrier when the caregiver reads Bangla.

**A known limitation:** CareMap requires structured clinical data as input. In the US and assisted living settings, this data already exists in EHR systems. In India, where paper records dominate, data entry remains a gap. CareMap is complete and functional today for any setting with structured data. As a next step, I am exploring multimodal data extraction — using models to read medication records from pill strip images and lab results from PDF reports — to close the paper-to-digital gap for India (via the [Amazon Nova Multimodal Challenge](https://amazon-nova.devpost.com/)).

On the **provider side**, India has one radiologist per 100,000 patients. Average X-ray report turnaround is 72 hours. Critical findings — pulmonary edema, pneumothorax — wait in the same queue as normal studies. Clinical labs generate 1,000+ HL7 messages per day; a potassium of 6.5 (life-threatening) can sit unread behind routine results.

**Applicability beyond India.** CareMap works wherever good EHR data exists — US Senior Assisted Living facilities face the same caregiver rotation problem, and large institutions like Sharp, Scripps, and Rendr have massive HL7 ORU volumes that CareMap's triage modules can help prioritize.

**Impact potential:** India has 80+ million family caregivers; the US has 53 million. CareMap targets two leverage points:

1. **Caregiver medication errors** — the #1 preventable cause of hospital readmission. A fridge sheet that survives caregiver turnover eliminates the verbal handoff problem.
2. **Triage queue prioritization** — routing critical cases to the front of a 500-study radiology queue or 1,000-message HL7 inbox means treatment in hours instead of days.

---

### Overall Solution

CareMap demonstrates that **a single clinical AI model (MedGemma 1.5 4B-IT) can serve both sides of healthcare** — patients and providers — through three modules that exploit different capabilities of the same model.

**Module 1: Fridge Sheet Generator (Patient Side — Text Reasoning)**

MedGemma interprets medications, labs, care gaps, and imaging reports, transforming clinical jargon into plain language at a 6th-grade reading level. The output is five printable 8.5x11" pages designed for the kitchen wall:

- Page 1: Medication schedule with time/food badges (for Ayah)
- Page 2: Lab results in plain language (for family)
- Page 3: Care actions in Today/This Week/Later buckets (for family)
- Page 4: Imaging findings explained simply (for family)
- Page 5: How medications, labs, and actions connect (for both)

MedGemma generates "Ask the Doctor" prompts so families know *what questions to ask* — addressing the gap Dr. Mishra identified: families don't know what they don't know. For example, for a high INR result, MedGemma generates: *"Ask the doctor: How often should this blood test be repeated?"* Multilingual translation via Meta's NLLB-200 (separate from MedGemma) supports Bengali, Hindi, and 8 other languages, preserving medication names and doses as safety-critical untranslated elements. Translation includes automated back-translation validation that flags content loss — particularly for medication warnings and negation words. The translation layer is lightweight and intentionally decoupled — it demonstrates how MedGemma's plain-language output can be effectively extended for maximum impact across the patient's entire caregiving circle, regardless of language.

**Module 2: Radiology Triage (Provider Side — Multimodal)**

This is where MedGemma's multimodal capability becomes essential. MedGemma analyzes chest X-rays and detects findings (edema, consolidation, cardiomegaly). A physician-auditable rule engine then maps findings to clinical priority levels (STAT / SOON / ROUTINE).

This divide-and-conquer architecture emerged from a key insight: MedGemma 1.5 is excellent at *visual finding detection* but poor at *priority assignment* (0% STAT recall when given both tasks). By decoupling perception from decision-making — using the model for what it's best at (pattern recognition) and clinical rules for what humans are best at (urgency judgment) — we achieved 100% STAT recall. The rules are a single CSV file that a clinician can review and adjust without touching code.

**Module 3: HL7 Message Triage (Provider Side — Text Reasoning)**

MedGemma triages incoming lab results by urgency, surfacing critical values (e.g., Troponin elevation, dangerous potassium levels) above routine results. This directly addresses the 1,000+ daily messages that clinical staff must process.

**Why MedGemma specifically?** MedGemma is trained on clinical text including EHR data, giving it domain understanding that general-purpose models lack. It interprets sig codes ("PO BID AC" to "by mouth, twice daily, before meals"), understands lab significance, and identifies radiological findings — all from a single 4B model that runs on a T4 GPU.

---

### Technical Details

**Architecture:** All three modules share a single `MedGemmaClient` that auto-detects MedGemma v1 vs v1.5 and selects the optimal dtype per device (bfloat16 for CUDA, float32 for MPS/CPU). Prompt templates use domain-specific JSON schemas with deterministic validation. A `SafetyValidator` enforces forbidden terms (no diagnosis, no jargon, no raw numeric values) on every output. The codebase includes 226+ unit tests with mocked MedGemma calls, golden test specifications for each module, and a modular architecture where each interpreter is independently testable.

**Proof-of-Architecture Validation (Kaggle T4 GPU):**

The following results are from curated test scenarios that validate the architecture's design, not a clinical trial. Sample sizes are small by design — the contribution is the *framework* (divide-and-conquer, physician-auditable rules, safety-first validation), not benchmark numbers.

| Module | N | Primary Metric | Score |
|--------|---|----------------|-------|
| Radiology Triage | 26 chest X-rays | STAT Recall | **100%** (3/3) |
| Radiology Triage | 26 chest X-rays | Overall Accuracy | 50% |
| HL7 Triage | 20 ORU messages | Overall Accuracy | 85% |
| Medication Interp. | 8 medications | Safety Pass Rate | 100% |
| Lab Interp. | 8 golden scenarios | No Forbidden Terms | 100% |

Total: 62 MedGemma inference calls across 4 modules in ~29 minutes on T4.

**Honest limitations:** Radiology overall accuracy is 50% due to deliberate over-triage — the rule engine escalates some SOON/ROUTINE cases to higher priority. In clinical practice, over-triage is strongly preferred over under-triage (a false STAT is an inconvenience; a missed STAT is a death). The rule CSV is designed for iterative refinement with clinician input — our notebook includes a diagnostic cell showing exactly which rules fired on each misclassified case, making the path to improvement transparent. LLM outputs are non-deterministic; scores represent a single evaluation pass.

**Resilient validation:** MedGemma 1.5 sometimes omits JSON keys non-deterministically. Rather than failing, `require_keys_with_defaults()` fills missing keys with safe fallback text, ensuring the fridge sheet always renders.

**Deployment stack:**
- **Kaggle notebook** — full end-to-end reproducible pipeline (the competition deliverable)
- **HuggingFace Spaces** — interactive Gradio demo for live exploration
- **Printable HTML** — the actual deliverable to caregivers; no app required, no internet required, works on any printer

**Deployment challenges and mitigations:**
1. *Runtime:* On a T4 GPU, batch processing takes ~10 minutes. In practice, healthcare settings have natural wait times between patient checkout and departure — fridge sheet generation runs as a background job during this window. Near-realtime is not required for the use case, and production deployments on higher-powered GPUs would be significantly faster.
2. *Model non-determinism:* Resilient validation with safe defaults ensures output always renders, even when MedGemma omits keys.
3. *Offline use:* The final artifact is static HTML. Once printed, it requires zero technology.

**Safety by design:** CareMap never diagnoses, never recommends treatment, never displays raw lab values. It fails closed — omitting information rather than speculating. Emergency contacts and "call 911" instructions are hardcoded, never model-generated. CareMap is designed as a caregiver support aid, not a clinical decision system — it does not meet the definition of a Software as a Medical Device (SaMD) because it never makes autonomous clinical decisions. All outputs require human review, and the system explicitly defers to clinicians on all diagnostic and treatment questions. The entire safety posture is documented in `SAFETY_AND_LIMITATIONS.md`.

---

**Source Code:** [github.com/codekunoichi/caremap-medgemma](https://github.com/codekunoichi/caremap-medgemma)
**Live Demo:** [HuggingFace Spaces](https://huggingface.co/spaces/codekunoichi/caremap-medgemma)
**Video Demo:** [link TBD]
