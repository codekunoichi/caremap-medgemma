"""
CareMap: EHR Enhancement Platform
HuggingFace Spaces Gradio App

Two modules powered by MedGemma:
1. Patient Portal - Caregiver-friendly Fridge Sheets
2. Clinical Staff - Radiology Triage Queue
"""

import json
import gradio as gr
from pathlib import Path
from dataclasses import dataclass

# Import CareMap modules
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from caremap.llm_client import MedGemmaClient
from caremap.lab_interpretation import interpret_lab
from caremap.medication_interpretation import interpret_medication_v3_grounded
from caremap.imaging_interpretation import interpret_imaging_report
from caremap.caregap_interpretation import interpret_caregap
from caremap.prompt_loader import load_prompt
from caremap.translation import (
    NLLBTranslator,
    LANGUAGE_CODES,
    LANGUAGE_NAMES,
)


# Global clients (loaded once)
medgemma_client = None
medgemma_multimodal_client = None
translator = None

# Language options for dropdown
LANGUAGE_OPTIONS = [
    ("English", "english"),
    ("Español (Spanish)", "spanish"),
    ("हिन्दी (Hindi)", "hindi"),
    ("বাংলা (Bengali)", "bengali"),
    ("中文简体 (Chinese Simplified)", "chinese_simplified"),
    ("中文繁體 (Chinese Traditional)", "chinese_traditional"),
    ("Português (Portuguese)", "portuguese"),
    ("தமிழ் (Tamil)", "tamil"),
    ("తెలుగు (Telugu)", "telugu"),
    ("मराठी (Marathi)", "marathi"),
]


def get_medgemma():
    """Lazy load the MedGemma client (text only)."""
    global medgemma_client
    if medgemma_client is None:
        print("Loading MedGemma model (text)...")
        medgemma_client = MedGemmaClient()
        print("MedGemma loaded!")
    return medgemma_client


def get_medgemma_multimodal():
    """Lazy load the MedGemma client with multimodal support."""
    global medgemma_multimodal_client
    if medgemma_multimodal_client is None:
        print("Loading MedGemma model (multimodal)...")
        medgemma_multimodal_client = MedGemmaClient(enable_multimodal=True)
        print("MedGemma multimodal loaded!")
    return medgemma_multimodal_client


def get_translator():
    """Lazy load the NLLB translator."""
    global translator
    if translator is None:
        print("Loading NLLB translator...")
        translator = NLLBTranslator()
        print("Translator loaded!")
    return translator


def translate_text(text: str, target_lang: str) -> str:
    """Translate text to target language if not English."""
    if target_lang == "english" or not text.strip():
        return text

    trans = get_translator()
    target_code = LANGUAGE_CODES.get(target_lang, "eng_Latn")
    return trans.translate_to(text, target_code)


# Keep old function name for compatibility
def get_client():
    return get_medgemma()


# Example patient data for Patient Portal
EXAMPLE_PATIENT = '''{
  "patient": {
    "nickname": "Dadu",
    "age_range": "80s",
    "conditions_display": [
      "Type 2 Diabetes with kidney complications",
      "Congestive Heart Failure",
      "Atrial Fibrillation"
    ]
  },
  "medications": [
    {
      "medication_name": "Metformin",
      "sig_text": "Take 500mg twice daily with meals",
      "timing": "morning and evening, with food",
      "clinician_notes": "Monitor kidney function",
      "interaction_notes": "Hold 48 hours before CT scan with contrast"
    },
    {
      "medication_name": "Warfarin",
      "sig_text": "Take as directed based on INR results",
      "timing": "evening, same time each day",
      "clinician_notes": "Target INR 2.0-3.0 for AFib",
      "interaction_notes": "Avoid NSAIDs. Keep vitamin K intake consistent."
    },
    {
      "medication_name": "Furosemide",
      "sig_text": "Take 40mg twice daily",
      "timing": "morning and early afternoon",
      "clinician_notes": "For heart failure fluid management",
      "interaction_notes": "Can cause low potassium"
    }
  ],
  "results": [
    {
      "test_name": "INR (Blood Thinner Level)",
      "meaning_category": "Needs follow-up",
      "source_note": "Above target range"
    },
    {
      "test_name": "Kidney Function",
      "meaning_category": "Slightly off",
      "source_note": "Stable from previous"
    }
  ],
  "care_gaps": [
    {
      "item_text": "Daily weight check for fluid monitoring",
      "next_step": "Weigh daily - call if gain more than 3 lbs in a day",
      "time_bucket": "Today"
    },
    {
      "item_text": "Diabetic eye exam overdue",
      "next_step": "Schedule appointment with eye doctor",
      "time_bucket": "This Week"
    }
  ],
  "contacts": {
    "clinic_name": "Riverside Internal Medicine",
    "clinic_phone": "555-0100",
    "pharmacy_name": "Care Plus Pharmacy",
    "pharmacy_phone": "555-0200"
  }
}'''


def generate_fridge_sheet(patient_json: str, language: str = "english", view_mode: str = "detailed", progress=gr.Progress()) -> str:
    """
    Generate a caregiver fridge sheet from patient JSON data.
    """
    is_detailed = (view_mode == "detailed")
    try:
        data = json.loads(patient_json)
    except json.JSONDecodeError as e:
        return f"**Error:** Invalid JSON\n\n```\n{str(e)}\n```"

    progress(0.1, desc="Loading model...")
    medgemma = get_client()

    lang_display = dict(LANGUAGE_OPTIONS).get(language, language)
    if language != "english":
        lang_display = f" ({lang_display})"
    else:
        lang_display = ""

    patient = data.get('patient', {})
    medications = data.get('medications', [])
    results = data.get('results', [])
    care_gaps = data.get('care_gaps', [])
    contacts = data.get('contacts', {})

    lines = []

    # Header
    nickname = patient.get('nickname', 'Patient')
    age = patient.get('age_range', '')
    conditions = patient.get('conditions_display', [])

    lines.append(f"# 🏠 CareMap Fridge Sheet: {nickname}")
    if is_detailed:
        lines.append("*📖 Detailed View - Full AI-powered explanations*")
    else:
        lines.append("*📋 Brief View - Printable summary*")
    lines.append("")
    if age:
        lines.append(f"**Age:** {age}")
    if conditions:
        lines.append(f"**Conditions:** {', '.join(conditions)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Care Gaps by urgency
    if care_gaps:
        progress(0.2, desc="Processing care gaps...")
        today_items = []
        week_items = []

        for i, gap in enumerate(care_gaps):
            progress(0.2 + (0.2 * i / len(care_gaps)), desc=f"Care gap {i+1}/{len(care_gaps)}")
            try:
                result = interpret_caregap(
                    client=medgemma,
                    item_text=gap.get('item_text', ''),
                    next_step=gap.get('next_step', ''),
                    time_bucket=gap.get('time_bucket', 'This Week'),
                )
                action = result.get('action_item', gap.get('item_text', ''))
                why_matters = result.get('why_this_matters', '')
                how_to = result.get('how_to_do_it', '')
            except Exception:
                action = gap.get('item_text', '')
                why_matters = ''
                how_to = ''

            bucket = gap.get('time_bucket', 'This Week')
            item_data = {
                'action': action,
                'why_matters': why_matters,
                'how_to': how_to,
                'next_step': gap.get('next_step', ''),
            }
            if bucket == 'Today':
                today_items.append(item_data)
            else:
                week_items.append(item_data)

        if today_items:
            lines.append("## 🚨 Today's Priorities")
            for item in today_items:
                if is_detailed:
                    lines.append(f"- [ ] **{item['action']}**")
                    if item['why_matters']:
                        lines.append(f"  - *Why:* {item['why_matters']}")
                    if item['how_to']:
                        lines.append(f"  - *How:* {item['how_to']}")
                    elif item['next_step']:
                        lines.append(f"  - *Next step:* {item['next_step']}")
                else:
                    lines.append(f"- [ ] **{item['action']}**")
            lines.append("")

        if week_items:
            lines.append("## 📅 This Week")
            for item in week_items:
                if is_detailed:
                    lines.append(f"- [ ] {item['action']}")
                    if item['why_matters']:
                        lines.append(f"  - *Why:* {item['why_matters']}")
                    if item['how_to']:
                        lines.append(f"  - *How:* {item['how_to']}")
                    elif item['next_step']:
                        lines.append(f"  - *Next step:* {item['next_step']}")
                else:
                    lines.append(f"- [ ] {item['action']}")
            lines.append("")

    # Medications
    if medications:
        progress(0.4, desc="Processing medications...")
        lines.append("## 💊 Medications")

        for i, med in enumerate(medications[:5]):
            progress(0.4 + (0.3 * i / min(len(medications), 5)), desc=f"Medication {i+1}")
            name = med.get('medication_name', 'Unknown')
            timing = med.get('timing', '')

            try:
                result, _ = interpret_medication_v3_grounded(
                    client=medgemma,
                    medication_name=name,
                    sig_text=med.get('sig_text', ''),
                    clinician_notes=med.get('clinician_notes', ''),
                    interaction_notes=med.get('interaction_notes', ''),
                )
                what_it_does = result.get('what_it_does', '')
                watch_out_for = result.get('watch_out_for', '')
                how_to_take = result.get('how_to_take', '')
                if 'raw_response' in result:
                    what_it_does = ''
                    watch_out_for = ''
                    how_to_take = ''
            except Exception:
                what_it_does = ''
                watch_out_for = ''
                how_to_take = ''

            lines.append(f"**{name}** ({timing})")
            if is_detailed:
                if what_it_does:
                    lines.append(f"- **What it does:** {what_it_does}")
                if how_to_take:
                    lines.append(f"- **How to take:** {how_to_take}")
                if watch_out_for:
                    lines.append(f"- ⚠️ **Watch out for:** {watch_out_for}")
                interaction = med.get('interaction_notes', '')
                if interaction:
                    lines.append(f"- 🔔 **Important:** {interaction}")
            else:
                if what_it_does:
                    lines.append(f"- {what_it_does[:150]}")
            lines.append("")

    # Labs
    if results:
        progress(0.7, desc="Processing lab results...")
        lines.append("## 🔬 Recent Labs")

        for i, lab in enumerate(results[:4]):
            progress(0.7 + (0.2 * i / min(len(results), 4)), desc=f"Lab {i+1}")
            name = lab.get('test_name', 'Unknown')
            category = lab.get('meaning_category', 'Normal')

            try:
                result = interpret_lab(
                    client=medgemma,
                    test_name=name,
                    meaning_category=category,
                    source_note=lab.get('source_note', ''),
                )
                meaning = result.get('what_it_means', category)
                what_to_ask = result.get('what_to_ask_doctor', '')
            except Exception:
                meaning = category
                what_to_ask = ''

            if is_detailed:
                lines.append(f"- **{name}** ({category})")
                if meaning:
                    lines.append(f"  - {meaning}")
                if what_to_ask:
                    lines.append(f"  - 💬 *Ask your doctor: {what_to_ask}*")
            else:
                brief_meaning = meaning.split('.')[0] + '.' if meaning else category
                lines.append(f"- **{name}**: {brief_meaning}")
        lines.append("")

    # Contacts
    if contacts:
        lines.append("## 📞 Contacts")
        clinic = contacts.get('clinic_name', '')
        clinic_phone = contacts.get('clinic_phone', '')
        pharmacy = contacts.get('pharmacy_name', '')
        pharmacy_phone = contacts.get('pharmacy_phone', '')

        if clinic:
            lines.append(f"- **Clinic:** {clinic} - {clinic_phone}")
        if pharmacy:
            lines.append(f"- **Pharmacy:** {pharmacy} - {pharmacy_phone}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*This sheet is for information only. Always confirm with your healthcare provider.*")

    english_output = "\n".join(lines)

    # Translate if not English
    if language != "english":
        progress(0.95, desc=f"Translating to {language}...")
        try:
            translated_lines = []
            for line in lines:
                if line.startswith("#") or line.startswith("---") or line == "":
                    if line.startswith("# "):
                        translated_lines.append("# " + translate_text(line[2:], language))
                    elif line.startswith("## "):
                        translated_lines.append("## " + translate_text(line[3:], language))
                    else:
                        translated_lines.append(line)
                elif line.startswith("- "):
                    translated_lines.append("- " + translate_text(line[2:], language))
                elif line.startswith("**"):
                    translated_lines.append(translate_text(line, language))
                elif line.startswith("*"):
                    translated_lines.append("*" + translate_text(line.strip("*"), language) + "*")
                else:
                    translated_lines.append(translate_text(line, language))
            output = "\n".join(translated_lines)
        except Exception as e:
            output = english_output + f"\n\n*(Translation to {language} failed: {str(e)})*"
    else:
        output = english_output

    progress(1.0, desc="Done!")
    return output


# ============================================================================
# RADIOLOGY TRIAGE MODULE
# ============================================================================

import re

def extract_json_from_response(text: str) -> dict:
    """Extract JSON object from LLM response."""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {
        "findings": ["Unable to parse findings"],
        "primary_impression": "Analysis incomplete",
        "priority": "STAT",
        "priority_reason": "Unable to complete analysis - defaulting to highest priority",
        "confidence": 0.0
    }


def analyze_single_xray(image, patient_age: int, patient_gender: str, progress=gr.Progress()) -> str:
    """
    Analyze a single chest X-ray and return triage results.
    """
    if image is None:
        return "Please upload a chest X-ray image."

    progress(0.2, desc="Loading MedGemma multimodal...")
    client = get_medgemma_multimodal()

    progress(0.4, desc="Analyzing X-ray...")

    # Build prompt
    prompt = f"""You are a clinical AI assistant helping to prioritize chest X-ray review queues.

Analyze this chest X-ray image and provide:
1. Key findings visible in the image
2. A priority level for radiologist review
3. Your confidence in the assessment

Patient Information:
- Age: {patient_age} years
- Gender: {"Male" if patient_gender == "M" else "Female"}

PRIORITY LEVELS:
- STAT: Critical findings requiring immediate review (< 1 hour) - e.g., pulmonary edema, large effusion, pneumothorax
- SOON: Abnormal findings requiring same-day review (< 24 hours) - e.g., cardiomegaly, consolidation, masses
- ROUTINE: Normal or minor findings (48-72 hours) - e.g., no acute abnormality

Respond ONLY with valid JSON in this exact format:
{{
  "findings": ["finding 1", "finding 2"],
  "primary_impression": "one sentence summary",
  "priority": "STAT" or "SOON" or "ROUTINE",
  "priority_reason": "brief explanation for priority level",
  "confidence": 0.0 to 1.0
}}

Important:
- Focus on clinically significant findings
- Be conservative - if uncertain, assign higher priority
- This is for TRIAGE ONLY - all images will be reviewed by a radiologist"""

    try:
        # Handle both file path and image object
        if isinstance(image, str):
            image_path = image
        else:
            # Gradio provides a temp file path
            image_path = image

        response = client.generate_with_images(prompt, images=[image_path])
        result = extract_json_from_response(response)
    except Exception as e:
        return f"**Error analyzing image:** {str(e)}"

    progress(0.9, desc="Formatting results...")

    # Format output
    priority = result.get('priority', 'STAT')
    priority_emoji = {'STAT': '🔴', 'SOON': '🟡', 'ROUTINE': '🟢'}.get(priority, '⚪')
    priority_label = {
        'STAT': 'STAT - Critical (Review < 1 hour)',
        'SOON': 'SOON - Abnormal (Review < 24 hours)',
        'ROUTINE': 'ROUTINE - Normal (Review 48-72 hours)'
    }.get(priority, priority)

    findings = result.get('findings', [])
    impression = result.get('primary_impression', 'No impression available')
    reason = result.get('priority_reason', '')
    confidence = result.get('confidence', 0.0)

    output = f"""# {priority_emoji} Triage Result: {priority}

## Priority Level
**{priority_label}**

{reason}

## Findings
"""
    for finding in findings:
        output += f"- {finding}\n"

    output += f"""
## Primary Impression
{impression}

## AI Confidence
{confidence:.0%}

---

⚠️ **Disclaimer:** This is an AI-assisted triage tool for prioritization only.
All images MUST be reviewed by a qualified radiologist.
AI confidence reflects model certainty, not diagnostic accuracy.

*Powered by MedGemma multimodal clinical AI*
"""

    progress(1.0, desc="Done!")
    return output


def run_demo_triage(progress=gr.Progress()) -> str:
    """
    Run triage on demo images to show the queue system.
    """
    # Check if demo images exist
    demo_dir = Path(__file__).parent.parent / "data" / "nih_chest_xray" / "demo_images"

    if not demo_dir.exists():
        return """**Demo images not available.**

To see the full triage demo, please:
1. Download NIH Chest X-ray sample images
2. Run the demo locally

Or upload your own chest X-ray image above.
"""

    progress(0.1, desc="Loading demo images...")
    client = get_medgemma_multimodal()

    # Load manifest
    manifest_path = Path(__file__).parent.parent / "data" / "nih_chest_xray" / "sample_manifest.csv"
    if not manifest_path.exists():
        return "Demo manifest not found."

    import pandas as pd
    manifest = pd.read_csv(manifest_path)

    # Analyze first few images from each category
    results = []
    stat_images = manifest[manifest['priority'] == 'STAT'].head(2)
    soon_images = manifest[manifest['priority'] == 'SOON'].head(2)
    routine_images = manifest[manifest['priority'] == 'ROUTINE'].head(2)

    demo_images = pd.concat([stat_images, soon_images, routine_images])
    total = len(demo_images)

    for idx, (_, row) in enumerate(demo_images.iterrows()):
        progress((idx + 1) / total * 0.8, desc=f"Analyzing {row['image_id']}...")

        image_path = demo_dir / row['priority'].lower() / row['image_id']
        if not image_path.exists():
            continue

        prompt = f"""Analyze this chest X-ray for a {row['patient_age']} year old {"male" if row['patient_gender'] == "M" else "female"}.

Provide findings and priority level (STAT/SOON/ROUTINE) as JSON:
{{"findings": [...], "primary_impression": "...", "priority": "...", "confidence": 0.0-1.0}}"""

        try:
            response = client.generate_with_images(prompt, images=[str(image_path)])
            result = extract_json_from_response(response)
            results.append({
                'image_id': row['image_id'],
                'ground_truth': row['findings'],
                'ai_priority': result.get('priority', 'STAT'),
                'ai_impression': result.get('primary_impression', ''),
                'ai_confidence': result.get('confidence', 0.0),
                'patient_info': f"{row['patient_age']}{row['patient_gender']}"
            })
        except Exception as e:
            print(f"Error analyzing {row['image_id']}: {e}")

    progress(0.9, desc="Formatting queue...")

    # Format as queue
    stat_results = [r for r in results if r['ai_priority'] == 'STAT']
    soon_results = [r for r in results if r['ai_priority'] == 'SOON']
    routine_results = [r for r in results if r['ai_priority'] == 'ROUTINE']

    output = f"""# 🏥 Radiology Triage Queue

**{len(results)} Studies Analyzed** | 🔴 {len(stat_results)} STAT | 🟡 {len(soon_results)} SOON | 🟢 {len(routine_results)} ROUTINE

---

## 🔴 STAT - Critical (Review < 1 hour)
"""
    for r in stat_results:
        output += f"""
**{r['image_id']}** | {r['patient_info']}
- AI: {r['ai_impression']}
- Confidence: {r['ai_confidence']:.0%}
- Ground Truth: {r['ground_truth']}
"""

    output += "\n## 🟡 SOON - Abnormal (Review < 24 hours)\n"
    for r in soon_results:
        output += f"""
**{r['image_id']}** | {r['patient_info']}
- AI: {r['ai_impression']}
- Confidence: {r['ai_confidence']:.0%}
- Ground Truth: {r['ground_truth']}
"""

    output += "\n## 🟢 ROUTINE - Normal (Review 48-72 hours)\n"
    for r in routine_results:
        output += f"""
**{r['image_id']}** | {r['patient_info']}
- AI: {r['ai_impression']}
- Confidence: {r['ai_confidence']:.0%}
- Ground Truth: {r['ground_truth']}
"""

    output += """
---

⚠️ **Important:** This is a DEMONSTRATION of AI-assisted triage.
- AI prioritizes the worklist order
- Human radiologists review ALL images
- AI does NOT replace clinical judgment

*Powered by MedGemma multimodal + NIH Chest X-ray Dataset*
"""

    progress(1.0, desc="Done!")
    return output


# ============================================================================
# GRADIO INTERFACE
# ============================================================================

with gr.Blocks(
    title="CareMap: EHR Enhancement Platform",
    theme=gr.themes.Soft(),
) as demo:

    gr.Markdown("""
    # 🏥 CareMap: EHR Enhancement Platform

    **One Model. Two Sides of Healthcare. Better Outcomes.**

    Powered by Google's MedGemma clinical foundation model.

    ---
    """)

    with gr.Tabs():
        # ================================================================
        # TAB 1: PATIENT PORTAL
        # ================================================================
        with gr.TabItem("👨‍👩‍👧 Patient Portal", id="patient-portal"):
            gr.Markdown("""
            ## Caregiver Fridge Sheet Generator

            Transform complex EHR data into caregiver-friendly one-page summaries.

            **Features:**
            - Medications explained with "Why It Matters"
            - Lab results in plain language
            - Care gaps prioritized by urgency
            - Supports 10 languages
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Patient Data (JSON)")
                    input_json = gr.Textbox(
                        label="Patient JSON",
                        placeholder="Paste patient JSON here...",
                        lines=15,
                        value=EXAMPLE_PATIENT,
                    )

                    gr.Markdown("### Options")
                    language_dropdown = gr.Dropdown(
                        label="Output Language",
                        choices=[label for label, _ in LANGUAGE_OPTIONS],
                        value="English",
                        interactive=True,
                    )

                    view_mode_radio = gr.Radio(
                        label="View Mode",
                        choices=[
                            ("📖 Detailed (Full AI Output)", "detailed"),
                            ("📋 Brief (Printable)", "brief"),
                        ],
                        value="detailed",
                        interactive=True,
                    )

                    with gr.Row():
                        generate_btn = gr.Button("Generate Fridge Sheet", variant="primary", size="lg")
                        clear_btn = gr.Button("Clear", size="lg")

                with gr.Column(scale=1):
                    gr.Markdown("### Fridge Sheet Output")
                    output_md = gr.Markdown(
                        label="Fridge Sheet",
                        value="*Click 'Generate Fridge Sheet' to see output*",
                    )

            def get_lang_code(display_name):
                for label, code in LANGUAGE_OPTIONS:
                    if label == display_name:
                        return code
                return "english"

            generate_btn.click(
                fn=lambda json_str, lang, mode: generate_fridge_sheet(json_str, get_lang_code(lang), mode),
                inputs=[input_json, language_dropdown, view_mode_radio],
                outputs=[output_md],
            )

            clear_btn.click(
                fn=lambda: ("", "English", "detailed", "*Click 'Generate Fridge Sheet' to see output*"),
                outputs=[input_json, language_dropdown, view_mode_radio, output_md],
            )

        # ================================================================
        # TAB 2: RADIOLOGY TRIAGE
        # ================================================================
        with gr.TabItem("👨‍⚕️ Radiology Triage", id="radiology-triage"):
            gr.Markdown("""
            ## AI-Assisted Radiology Triage Queue

            MedGemma analyzes chest X-rays and prioritizes the review queue by severity.

            **Priority Levels:**
            - 🔴 **STAT** - Critical findings (review < 1 hour)
            - 🟡 **SOON** - Abnormal findings (review < 24 hours)
            - 🟢 **ROUTINE** - Normal/minor findings (review 48-72 hours)

            **Important:** AI prioritizes the worklist order. Radiologists review ALL images.
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Upload X-ray")
                    xray_input = gr.Image(
                        label="Chest X-ray Image",
                        type="filepath",
                        height=300,
                    )

                    with gr.Row():
                        patient_age = gr.Number(
                            label="Patient Age",
                            value=55,
                            minimum=0,
                            maximum=120,
                        )
                        patient_gender = gr.Radio(
                            label="Gender",
                            choices=[("Male", "M"), ("Female", "F")],
                            value="M",
                        )

                    analyze_btn = gr.Button("Analyze X-ray", variant="primary", size="lg")

                    gr.Markdown("---")
                    gr.Markdown("### Or Run Demo Queue")
                    demo_btn = gr.Button("Run Demo Triage (6 images)", variant="secondary", size="lg")

                with gr.Column(scale=1):
                    gr.Markdown("### Triage Results")
                    triage_output = gr.Markdown(
                        label="Triage Result",
                        value="*Upload an X-ray or run demo to see results*",
                    )

            analyze_btn.click(
                fn=analyze_single_xray,
                inputs=[xray_input, patient_age, patient_gender],
                outputs=[triage_output],
            )

            demo_btn.click(
                fn=run_demo_triage,
                outputs=[triage_output],
            )

    gr.Markdown("""
    ---

    ## About CareMap

    **CareMap enhances existing EHRs with clinical AI** - it doesn't replace your system, it makes it smarter.

    | Module | For | What It Does |
    |--------|-----|--------------|
    | **Patient Portal** | Caregivers & Families | Translates complex EHR data into plain-language "Fridge Sheets" |
    | **Radiology Triage** | Radiologists & Clinicians | Prioritizes imaging worklist by AI-detected severity |

    ### Why This Matters (Especially in India)
    - **1:100,000** - Radiologist-to-patient ratio in India
    - **72 hours** - Average X-ray report delay in district hospitals
    - **80%** - Caregivers who don't understand discharge instructions
    - **2x** - Readmission risk when caregivers aren't educated

    ---

    Built for [Kaggle Solve for India with Gemini](https://www.kaggle.com/competitions/solve-for-india-gemini) |
    Powered by Google's MedGemma |
    Demo only - Not for clinical use
    """)


if __name__ == "__main__":
    demo.launch()
