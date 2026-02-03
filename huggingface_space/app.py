"""
CareMap: EHR Enhancement Platform
HuggingFace Spaces Gradio App

Three modules powered by MedGemma:
1. Patient Portal - Caregiver-friendly Fridge Sheets
2. Clinical Staff - Radiology Triage Queue (Multimodal)
3. Clinical Staff - HL7 ORU Message Triage (Text)
"""

import json
import gradio as gr
from pathlib import Path
from dataclasses import dataclass
import re

# Import CareMap modules
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from caremap.llm_client import MedGemmaClient
from caremap.lab_interpretation import interpret_lab
from caremap.medication_interpretation import interpret_medication_v3_grounded
from caremap.imaging_interpretation import interpret_imaging_report
from caremap.caregap_interpretation import interpret_caregap
from caremap.prompt_loader import load_prompt, fill_prompt
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


# Example HL7 ORU messages for demo
EXAMPLE_HL7_MESSAGES = [
    {
        "message_id": "ORU-001",
        "message_type": "LAB",
        "patient": {"id": "P001", "age": 67, "gender": "M"},
        "clinical_context": "Patient on ACE inhibitor and potassium-sparing diuretic",
        "observations": [
            {"test_name": "Potassium", "value": "6.8", "units": "mEq/L", "reference_range": "3.5-5.0", "abnormal_flag": "HH"}
        ]
    },
    {
        "message_id": "ORU-002",
        "message_type": "LAB",
        "patient": {"id": "P002", "age": 45, "gender": "F"},
        "clinical_context": "Chest pain, rule out MI",
        "observations": [
            {"test_name": "Troponin I", "value": "2.45", "units": "ng/mL", "reference_range": "<0.04", "abnormal_flag": "HH"},
            {"test_name": "CK-MB", "value": "45", "units": "U/L", "reference_range": "0-25", "abnormal_flag": "H"}
        ]
    },
    {
        "message_id": "ORU-003",
        "message_type": "LAB",
        "patient": {"id": "P003", "age": 55, "gender": "M"},
        "clinical_context": "AFib patient on warfarin, routine monitoring",
        "observations": [
            {"test_name": "INR", "value": "4.2", "units": "", "reference_range": "2.0-3.0", "abnormal_flag": "H"}
        ]
    },
    {
        "message_id": "ORU-004",
        "message_type": "LAB",
        "patient": {"id": "P004", "age": 42, "gender": "F"},
        "clinical_context": "Annual wellness exam",
        "observations": [
            {"test_name": "Glucose, Fasting", "value": "92", "units": "mg/dL", "reference_range": "70-100", "abnormal_flag": ""},
            {"test_name": "Total Cholesterol", "value": "195", "units": "mg/dL", "reference_range": "<200", "abnormal_flag": ""}
        ]
    },
    {
        "message_id": "ORU-005",
        "message_type": "RADIOLOGY",
        "patient": {"id": "P005", "age": 58, "gender": "M"},
        "clinical_context": "Sudden onset dyspnea and chest pain",
        "observations": [
            {"test_name": "Chest X-ray", "value": "IMPRESSION: Large left-sided pneumothorax with complete collapse of the left lung. Mediastinal shift to the right. Recommend emergent decompression.", "value_type": "TEXT", "abnormal_flag": "A"}
        ]
    },
    {
        "message_id": "ORU-006",
        "message_type": "LAB",
        "patient": {"id": "P006", "age": 35, "gender": "M"},
        "clinical_context": "Pre-employment physical",
        "observations": [
            {"test_name": "WBC", "value": "7.2", "units": "10*3/uL", "reference_range": "4.5-11.0", "abnormal_flag": ""},
            {"test_name": "Hemoglobin", "value": "14.5", "units": "g/dL", "reference_range": "13.5-17.5", "abnormal_flag": ""},
            {"test_name": "Platelet Count", "value": "245", "units": "10*3/uL", "reference_range": "150-400", "abnormal_flag": ""}
        ]
    }
]


def generate_fridge_sheet(patient_json: str, language: str = "english", view_mode: str = "detailed", progress=gr.Progress()) -> str:
    """Generate a caregiver fridge sheet from patient JSON data."""
    is_detailed = (view_mode == "detailed")
    try:
        data = json.loads(patient_json)
    except json.JSONDecodeError as e:
        return f"**Error:** Invalid JSON\n\n```\n{str(e)}\n```"

    progress(0.1, desc="Loading model...")
    medgemma = get_client()

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

    # Care Gaps
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
            item_data = {'action': action, 'why_matters': why_matters, 'how_to': how_to, 'next_step': gap.get('next_step', '')}
            if bucket == 'Today':
                today_items.append(item_data)
            else:
                week_items.append(item_data)

        if today_items:
            lines.append("## 🚨 Today's Priorities")
            for item in today_items:
                lines.append(f"- [ ] **{item['action']}**")
                if is_detailed and item['why_matters']:
                    lines.append(f"  - *Why:* {item['why_matters']}")
            lines.append("")

        if week_items:
            lines.append("## 📅 This Week")
            for item in week_items:
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
                    client=medgemma, medication_name=name,
                    sig_text=med.get('sig_text', ''),
                    clinician_notes=med.get('clinician_notes', ''),
                    interaction_notes=med.get('interaction_notes', ''),
                )
                what_it_does = result.get('what_it_does', '') if 'raw_response' not in result else ''
            except Exception:
                what_it_does = ''
            lines.append(f"**{name}** ({timing})")
            if what_it_does:
                lines.append(f"- {what_it_does[:150]}")
            lines.append("")

    # Labs
    if results:
        progress(0.7, desc="Processing lab results...")
        lines.append("## 🔬 Recent Labs")
        for i, lab in enumerate(results[:4]):
            name = lab.get('test_name', 'Unknown')
            category = lab.get('meaning_category', 'Normal')
            lines.append(f"- **{name}**: {category}")
        lines.append("")

    # Contacts
    if contacts:
        lines.append("## 📞 Contacts")
        if contacts.get('clinic_name'):
            lines.append(f"- **Clinic:** {contacts['clinic_name']} - {contacts.get('clinic_phone', '')}")
        if contacts.get('pharmacy_name'):
            lines.append(f"- **Pharmacy:** {contacts['pharmacy_name']} - {contacts.get('pharmacy_phone', '')}")
        lines.append("")

    lines.append("---")
    lines.append("*This sheet is for information only. Always confirm with your healthcare provider.*")

    output = "\n".join(lines)

    # Translate if needed
    if language != "english":
        progress(0.95, desc=f"Translating to {language}...")
        try:
            translated_lines = []
            for line in lines:
                if line.startswith("#") or line.startswith("---") or line == "":
                    translated_lines.append(line)
                elif line.startswith("- "):
                    translated_lines.append("- " + translate_text(line[2:], language))
                else:
                    translated_lines.append(translate_text(line, language))
            output = "\n".join(translated_lines)
        except Exception as e:
            output += f"\n\n*(Translation failed: {str(e)})*"

    progress(1.0, desc="Done!")
    return output


# ============================================================================
# RADIOLOGY TRIAGE MODULE
# ============================================================================

def extract_json_from_response(text: str) -> dict:
    """Extract JSON object from LLM response."""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {
        "priority": "STAT",
        "priority_reason": "Unable to parse - defaulting to highest priority",
        "key_findings": ["Analysis incomplete"],
        "confidence": 0.0
    }


def analyze_single_xray(image, patient_age: int, patient_gender: str, progress=gr.Progress()) -> str:
    """Analyze a single chest X-ray and return triage results."""
    if image is None:
        return "Please upload a chest X-ray image."

    progress(0.2, desc="Loading MedGemma multimodal...")
    client = get_medgemma_multimodal()

    progress(0.4, desc="Analyzing X-ray...")

    prompt = f"""You are a clinical AI assistant helping to prioritize chest X-ray review queues.

Analyze this chest X-ray image and provide:
1. Key findings visible in the image
2. A priority level for radiologist review
3. Your confidence in the assessment

Patient Information:
- Age: {patient_age} years
- Gender: {"Male" if patient_gender == "M" else "Female"}

PRIORITY LEVELS:
- STAT: Critical findings requiring immediate review (< 1 hour)
- SOON: Abnormal findings requiring same-day review (< 24 hours)
- ROUTINE: Normal or minor findings (48-72 hours)

Respond ONLY with valid JSON:
{{"findings": [...], "primary_impression": "...", "priority": "STAT/SOON/ROUTINE", "priority_reason": "...", "confidence": 0.0-1.0}}"""

    try:
        image_path = image if isinstance(image, str) else image
        response = client.generate_with_images(prompt, images=[image_path])
        result = extract_json_from_response(response)
    except Exception as e:
        return f"**Error analyzing image:** {str(e)}"

    progress(0.9, desc="Formatting results...")

    priority = result.get('priority', 'STAT')
    priority_emoji = {'STAT': '🔴', 'SOON': '🟡', 'ROUTINE': '🟢'}.get(priority, '⚪')

    output = f"""# {priority_emoji} Triage Result: {priority}

## Priority Level
**{priority}** - {result.get('priority_reason', '')}

## Findings
"""
    for finding in result.get('findings', []):
        output += f"- {finding}\n"

    output += f"""
## AI Confidence
{result.get('confidence', 0):.0%}

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All images MUST be reviewed by a radiologist.
"""

    progress(1.0, desc="Done!")
    return output


# ============================================================================
# HL7 ORU TRIAGE MODULE
# ============================================================================

def format_observations_text(observations: list) -> str:
    """Format observations for the prompt."""
    lines = []
    for obs in observations:
        if obs.get('value_type') == 'TEXT':
            lines.append(f"- {obs['test_name']}: {obs['value']}")
        else:
            flag = f" [{obs.get('abnormal_flag', '')}]" if obs.get('abnormal_flag') else ""
            ref = f" (ref: {obs.get('reference_range', '')})" if obs.get('reference_range') else ""
            lines.append(f"- {obs['test_name']}: {obs['value']} {obs.get('units', '')}{ref}{flag}")
    return "\n".join(lines)


def triage_single_hl7(message: dict, progress=gr.Progress()) -> str:
    """Triage a single HL7 ORU message."""
    progress(0.2, desc="Loading MedGemma...")
    client = get_medgemma()

    progress(0.4, desc="Analyzing message...")

    patient = message.get('patient', {})
    observations_text = format_observations_text(message.get('observations', []))

    prompt = f"""You are a clinical AI assistant helping to triage incoming HL7 ORU messages.

MESSAGE DETAILS:
- Message Type: {message.get('message_type', 'LAB')}
- Patient: {patient.get('age', 'Unknown')} year old {"Male" if patient.get('gender') == "M" else "Female"}
- Clinical Context: {message.get('clinical_context', 'Not provided')}

OBSERVATIONS:
{observations_text}

PRIORITY LEVELS:
- STAT: Life-threatening or critical values (< 1 hour) - e.g., K+ >6.5, troponin elevation, severe anemia
- SOON: Abnormal results requiring same-day review (< 24 hours) - e.g., elevated INR, worsening renal
- ROUTINE: Normal results or minor abnormalities (48-72 hours)

Respond ONLY with valid JSON:
{{"priority": "STAT/SOON/ROUTINE", "priority_reason": "...", "key_findings": [...], "recommended_action": "...", "confidence": 0.0-1.0}}"""

    try:
        response = client.generate(prompt)
        result = extract_json_from_response(response)
    except Exception as e:
        return f"**Error:** {str(e)}"

    progress(0.9, desc="Formatting results...")

    priority = result.get('priority', 'STAT')
    priority_emoji = {'STAT': '🔴', 'SOON': '🟡', 'ROUTINE': '🟢'}.get(priority, '⚪')

    output = f"""# {priority_emoji} HL7 Triage Result: {priority}

## Message: {message.get('message_id', 'Unknown')}
**Type:** {message.get('message_type', 'LAB')} | **Patient:** {patient.get('age', '?')} {patient.get('gender', '?')}

## Priority Reason
{result.get('priority_reason', 'N/A')}

## Key Findings
"""
    for finding in result.get('key_findings', []):
        output += f"- {finding}\n"

    output += f"""
## Recommended Action
{result.get('recommended_action', 'N/A')}

## AI Confidence
{result.get('confidence', 0):.0%}

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
"""

    progress(1.0, desc="Done!")
    return output


def triage_batch_hl7(progress=gr.Progress()) -> str:
    """Triage batch of demo HL7 messages."""
    progress(0.1, desc="Loading MedGemma...")
    client = get_medgemma()

    messages = EXAMPLE_HL7_MESSAGES
    results = []

    for idx, msg in enumerate(messages):
        progress((idx + 1) / len(messages) * 0.8, desc=f"Triaging {msg['message_id']}...")

        patient = msg.get('patient', {})
        observations_text = format_observations_text(msg.get('observations', []))

        prompt = f"""Triage this clinical result:
Patient: {patient.get('age')} {patient.get('gender')} | Context: {msg.get('clinical_context')}
Observations:
{observations_text}

Respond with JSON: {{"priority": "STAT/SOON/ROUTINE", "priority_reason": "...", "confidence": 0.0-1.0}}"""

        try:
            response = client.generate(prompt)
            result = extract_json_from_response(response)
            results.append({
                'message_id': msg['message_id'],
                'message_type': msg['message_type'],
                'patient': f"{patient.get('age', '?')}{patient.get('gender', '?')}",
                'priority': result.get('priority', 'STAT'),
                'reason': result.get('priority_reason', ''),
                'confidence': result.get('confidence', 0)
            })
        except Exception as e:
            results.append({
                'message_id': msg['message_id'],
                'message_type': msg['message_type'],
                'patient': f"{patient.get('age', '?')}{patient.get('gender', '?')}",
                'priority': 'STAT',
                'reason': f'Error: {str(e)}',
                'confidence': 0
            })

    progress(0.9, desc="Formatting queue...")

    # Group by priority
    stat = [r for r in results if r['priority'] == 'STAT']
    soon = [r for r in results if r['priority'] == 'SOON']
    routine = [r for r in results if r['priority'] == 'ROUTINE']

    output = f"""# 🏥 HL7 ORU Triage Queue

**{len(results)} Messages Analyzed** | 🔴 {len(stat)} STAT | 🟡 {len(soon)} SOON | 🟢 {len(routine)} ROUTINE

---

## 🔴 STAT - Critical (Review < 1 hour)
"""
    for r in stat:
        output += f"**{r['message_id']}** | {r['message_type']} | {r['patient']} | {r['confidence']:.0%}\n"
        output += f"- {r['reason'][:80]}...\n\n"

    output += "\n## 🟡 SOON - Abnormal (Review < 24 hours)\n"
    for r in soon:
        output += f"**{r['message_id']}** | {r['message_type']} | {r['patient']} | {r['confidence']:.0%}\n"
        output += f"- {r['reason'][:80]}...\n\n"

    output += "\n## 🟢 ROUTINE - Normal (Review 48-72 hours)\n"
    for r in routine:
        output += f"**{r['message_id']}** | {r['message_type']} | {r['patient']} | {r['confidence']:.0%}\n"
        output += f"- {r['reason'][:80]}...\n\n"

    output += """
---
⚠️ **Important:** AI prioritizes the message queue. Clinicians review ALL results.

*Powered by MedGemma text reasoning*
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

    **One Model. Three Modules. Better Outcomes.**

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

            **Features:** Medications explained, Lab results in plain language, Care gaps prioritized, 10 languages supported
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    input_json = gr.Textbox(label="Patient JSON", lines=12, value=EXAMPLE_PATIENT)
                    language_dropdown = gr.Dropdown(label="Language", choices=[l for l, _ in LANGUAGE_OPTIONS], value="English")
                    view_mode_radio = gr.Radio(label="View", choices=[("Detailed", "detailed"), ("Brief", "brief")], value="detailed")
                    generate_btn = gr.Button("Generate Fridge Sheet", variant="primary", size="lg")

                with gr.Column(scale=1):
                    output_md = gr.Markdown(value="*Click 'Generate' to see output*")

            def get_lang_code(name):
                for l, c in LANGUAGE_OPTIONS:
                    if l == name:
                        return c
                return "english"

            generate_btn.click(
                fn=lambda j, l, m: generate_fridge_sheet(j, get_lang_code(l), m),
                inputs=[input_json, language_dropdown, view_mode_radio],
                outputs=[output_md],
            )

        # ================================================================
        # TAB 2: RADIOLOGY TRIAGE
        # ================================================================
        with gr.TabItem("🔬 Radiology Triage", id="radiology-triage"):
            gr.Markdown("""
            ## AI-Assisted Radiology Triage (Multimodal)

            MedGemma analyzes chest X-rays and prioritizes the review queue.

            🔴 **STAT** < 1 hour | 🟡 **SOON** < 24 hours | 🟢 **ROUTINE** 48-72 hours
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    xray_input = gr.Image(label="Upload Chest X-ray", type="filepath", height=250)
                    with gr.Row():
                        patient_age = gr.Number(label="Age", value=55, minimum=0, maximum=120)
                        patient_gender = gr.Radio(label="Gender", choices=[("M", "M"), ("F", "F")], value="M")
                    analyze_btn = gr.Button("Analyze X-ray", variant="primary", size="lg")

                with gr.Column(scale=1):
                    triage_output = gr.Markdown(value="*Upload an X-ray to see results*")

            analyze_btn.click(fn=analyze_single_xray, inputs=[xray_input, patient_age, patient_gender], outputs=[triage_output])

        # ================================================================
        # TAB 3: HL7 ORU TRIAGE
        # ================================================================
        with gr.TabItem("📋 HL7 Message Triage", id="hl7-triage"):
            gr.Markdown("""
            ## AI-Assisted HL7 ORU Triage (Text)

            MedGemma analyzes incoming lab results and clinical messages.

            🔴 **STAT** - Critical values (K+ >6.5, Troponin, etc.)
            🟡 **SOON** - Abnormal (elevated INR, worsening renal)
            🟢 **ROUTINE** - Normal results
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Select a Message to Triage")
                    message_dropdown = gr.Dropdown(
                        label="Sample HL7 Messages",
                        choices=[f"{m['message_id']} - {m['message_type']} - {m['clinical_context'][:40]}..." for m in EXAMPLE_HL7_MESSAGES],
                        value=f"{EXAMPLE_HL7_MESSAGES[0]['message_id']} - {EXAMPLE_HL7_MESSAGES[0]['message_type']} - {EXAMPLE_HL7_MESSAGES[0]['clinical_context'][:40]}..."
                    )
                    triage_single_btn = gr.Button("Triage Selected Message", variant="primary", size="lg")

                    gr.Markdown("---")
                    gr.Markdown("### Or Run Batch Triage")
                    triage_batch_btn = gr.Button("Triage All 6 Messages", variant="secondary", size="lg")

                with gr.Column(scale=1):
                    gr.Markdown("### Triage Results")
                    hl7_output = gr.Markdown(value="*Select a message or run batch triage*")

            def triage_selected(selection):
                msg_id = selection.split(" - ")[0]
                for msg in EXAMPLE_HL7_MESSAGES:
                    if msg['message_id'] == msg_id:
                        return triage_single_hl7(msg)
                return "Message not found"

            triage_single_btn.click(fn=triage_selected, inputs=[message_dropdown], outputs=[hl7_output])
            triage_batch_btn.click(fn=triage_batch_hl7, outputs=[hl7_output])

    gr.Markdown("""
    ---

    ## About CareMap

    **CareMap enhances existing EHRs with clinical AI** - it doesn't replace your system, it makes it smarter.

    | Module | For | MedGemma Mode |
    |--------|-----|---------------|
    | **Patient Portal** | Caregivers & Families | Text reasoning |
    | **Radiology Triage** | Radiologists | **Multimodal** (image + text) |
    | **HL7 Message Triage** | Lab/Clinical Staff | Text reasoning |

    ### Why This Matters (India Context)
    - **1:100,000** - Radiologist-to-patient ratio
    - **72 hours** - Average X-ray report delay
    - **1000+** - HL7 messages per day in busy hospitals

    ---

    Built for [Kaggle Solve for India with Gemini](https://www.kaggle.com/competitions/solve-for-india-gemini) |
    Powered by Google's MedGemma |
    Demo only - Not for clinical use
    """)


if __name__ == "__main__":
    demo.launch()
