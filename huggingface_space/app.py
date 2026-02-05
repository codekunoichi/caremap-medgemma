"""
CareMap: EHR Enhancement Platform
HuggingFace Spaces Gradio App

Three modules powered by MedGemma:
1. Patient Portal - Caregiver-friendly Fridge Sheets (Concept B: 5 printable pages)
2. Clinical Staff - Radiology Triage Queue (Multimodal)
3. Clinical Staff - HL7 ORU Message Triage (Text)
"""

import json
import gradio as gr
from pathlib import Path
from dataclasses import dataclass
import re
import tempfile
import base64

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
from caremap.html_translator import translate_fridge_sheet_html

# Import Concept B fridge sheet generators
from caremap.fridge_sheet_html import (
    generate_medications_page,
    generate_labs_page,
    generate_gaps_page,
    generate_imaging_page,
    generate_connections_page,
    PatientInfo,
)


# ============================================================================
# MEDICATION TABLE FORMATTING HELPERS
# ============================================================================

def get_time_emoji(timing: str) -> str:
    """Convert timing text to emoji badges."""
    timing_lower = timing.lower()
    badges = []

    if 'morning' in timing_lower or 'breakfast' in timing_lower or 'am' in timing_lower:
        badges.append('☀️ Morning')
    if 'afternoon' in timing_lower or 'lunch' in timing_lower or 'noon' in timing_lower:
        badges.append('🌤️ Afternoon')
    if 'evening' in timing_lower or 'dinner' in timing_lower or 'pm' in timing_lower:
        badges.append('🌅 Evening')
    if 'bedtime' in timing_lower or 'night' in timing_lower:
        badges.append('🌙 Bedtime')
    if 'twice' in timing_lower and not badges:
        badges = ['☀️ Morning', '🌅 Evening']

    return '<br>'.join(badges) if badges else timing


def get_food_instruction(timing: str, sig_text: str) -> str:
    """Extract food instructions from timing and sig text."""
    combined = (timing + ' ' + sig_text).lower()

    if 'with food' in combined or 'with meal' in combined or 'after meal' in combined:
        return '🍽️ With food'
    elif 'empty stomach' in combined or 'before food' in combined or 'before meal' in combined:
        return '🚫🍽️ Empty stomach'
    else:
        return '—'


def format_medication_table(medications: list, medgemma, progress_fn=None) -> str:
    """Generate a medication table in concept_b style."""
    lines = []
    lines.append("## 💊 Medication Schedule")
    lines.append("*Daily reference for giving medicines*")
    lines.append("")
    lines.append("| ✓ | Medicine | When | How | Why It Matters 🧠 | Watch For |")
    lines.append("|:---:|:---|:---|:---|:---|:---|")

    for i, med in enumerate(medications[:8]):  # Limit to 8 meds for one page
        if progress_fn:
            progress_fn(0.4 + (0.3 * i / min(len(medications), 8)), desc=f"Medication {i+1}")

        name = med.get('medication_name', 'Unknown')
        sig_text = med.get('sig_text', '')
        timing = med.get('timing', '')
        clinician_notes = med.get('clinician_notes', '')
        interaction_notes = med.get('interaction_notes', '')

        # Get time emoji
        when_col = get_time_emoji(timing)

        # Get food instruction
        how_col = get_food_instruction(timing, sig_text)

        # Get AI interpretation
        try:
            result, _ = interpret_medication_v3_grounded(
                client=medgemma,
                medication_name=name,
                sig_text=sig_text,
                clinician_notes=clinician_notes,
                interaction_notes=interaction_notes,
            )
            why_matters = result.get('what_this_does', '') if 'raw_response' not in result else ''
            watch_for = result.get('watch_out_for', '') if 'raw_response' not in result else ''
        except Exception:
            why_matters = clinician_notes
            watch_for = interaction_notes

        # Build watch for column (combine watch_for + interaction_notes if both exist)
        watch_items = []
        if watch_for:
            watch_items.append(watch_for)
        if interaction_notes and interaction_notes.lower() not in (watch_for or '').lower():
            watch_items.append(f"⚠️ {interaction_notes}")
        watch_col = ' '.join(watch_items)[:100] if watch_items else '—'

        # Clean up text for table (remove newlines, limit length)
        why_matters = (why_matters or '—')[:80].replace('\n', ' ').replace('|', '/')
        watch_col = watch_col.replace('\n', ' ').replace('|', '/')

        lines.append(f"| ☐ | **{name}** | {when_col} | {how_col} | {why_matters} | {watch_col} |")

    lines.append("")
    return "\n".join(lines)


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


# Example patient data for Patient Portal (matches golden_patient_complex.json)
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
      "sig_text": "Take 500mg by mouth twice daily with meals",
      "timing": "morning and evening, with food",
      "clinician_notes": "Monitor kidney function. Hold if eGFR drops below 30.",
      "interaction_notes": "Hold 48 hours before and after CT scan with contrast dye."
    },
    {
      "medication_name": "Warfarin",
      "sig_text": "Take as directed based on INR results",
      "timing": "evening, same time each day",
      "clinician_notes": "Target INR 2.0-3.0 for AFib. Weekly INR checks required.",
      "interaction_notes": "Avoid NSAIDs (ibuprofen, aspirin). Keep vitamin K intake consistent."
    },
    {
      "medication_name": "Furosemide",
      "sig_text": "Take 40mg by mouth twice daily",
      "timing": "morning and early afternoon, not after 4pm",
      "clinician_notes": "For heart failure fluid management. Weigh daily.",
      "interaction_notes": "Can cause low potassium. Take potassium supplement as prescribed."
    },
    {
      "medication_name": "Potassium Chloride",
      "sig_text": "Take 20mEq by mouth daily with food",
      "timing": "with breakfast",
      "clinician_notes": "To replace potassium lost from Lasix.",
      "interaction_notes": "Take with food to avoid stomach upset. Do not crush tablets."
    },
    {
      "medication_name": "Carvedilol",
      "sig_text": "Take 12.5mg by mouth twice daily with food",
      "timing": "morning and evening, with food",
      "clinician_notes": "Beta-blocker for heart failure and heart rate control.",
      "interaction_notes": "May cause dizziness. Rise slowly from sitting or lying down."
    },
    {
      "medication_name": "Lisinopril",
      "sig_text": "Take 10mg by mouth daily",
      "timing": "morning",
      "clinician_notes": "ACE inhibitor for heart and kidney protection.",
      "interaction_notes": "May cause dry cough. Can raise potassium levels."
    },
    {
      "medication_name": "Levothyroxine",
      "sig_text": "Take 75mcg by mouth daily on empty stomach",
      "timing": "first thing in morning, 60 minutes before food",
      "clinician_notes": "For hypothyroidism. Take on empty stomach.",
      "interaction_notes": "Separate from calcium, iron, antacids by at least 4 hours."
    },
    {
      "medication_name": "Acetaminophen",
      "sig_text": "Take 650mg by mouth every 6 hours as needed for pain",
      "timing": "as needed for arthritis pain",
      "clinician_notes": "Preferred pain reliever - safe with warfarin.",
      "interaction_notes": "Do NOT exceed 3000mg per day. Avoid ibuprofen, naproxen, aspirin."
    }
  ],
  "results": [
    {
      "test_name": "INR (Blood Thinner Level)",
      "meaning_category": "Needs follow-up",
      "source_note": "Above target range - warfarin dose may need adjustment"
    },
    {
      "test_name": "Kidney Function (eGFR)",
      "meaning_category": "Slightly off",
      "source_note": "Stable from previous - continue monitoring"
    },
    {
      "test_name": "Potassium Level",
      "meaning_category": "Normal",
      "source_note": "Within normal range"
    },
    {
      "test_name": "Hemoglobin A1c (3-Month Blood Sugar Average)",
      "meaning_category": "Needs follow-up",
      "source_note": "Above goal - discuss at next visit"
    },
    {
      "test_name": "BNP (Heart Strain Marker)",
      "meaning_category": "Slightly off",
      "source_note": "Elevated - watch for fluid buildup symptoms"
    },
    {
      "test_name": "TSH (Thyroid Function)",
      "meaning_category": "Normal",
      "source_note": "Thyroid well controlled on current dose"
    }
  ],
  "care_gaps": [
    {
      "item_text": "Daily weight check for fluid monitoring",
      "next_step": "Weigh daily - call if gain more than 3 lbs in a day",
      "time_bucket": "Today"
    },
    {
      "item_text": "Annual flu shot not received",
      "next_step": "Ask pharmacy about flu shot availability",
      "time_bucket": "Today"
    },
    {
      "item_text": "INR recheck needed - last result was high",
      "next_step": "Call clinic to schedule INR blood draw",
      "time_bucket": "This Week"
    },
    {
      "item_text": "Diabetic eye exam overdue by 8 months",
      "next_step": "Schedule appointment with eye doctor",
      "time_bucket": "This Week"
    },
    {
      "item_text": "Cardiology follow-up appointment due",
      "next_step": "Call heart doctor's office to schedule 3-month check",
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
    """Generate a caregiver fridge sheet from patient JSON data (legacy markdown version)."""
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

    # Medications - Use table format like concept_b_meds.html
    if medications:
        med_table = format_medication_table(
            medications,
            medgemma,
            progress_fn=lambda p, desc: progress(p, desc=desc)
        )
        lines.append(med_table)

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
# CONCEPT B: 5-PAGE PRINTABLE FRIDGE SHEETS
# ============================================================================

def generate_concept_b_page(
    patient_json: str,
    page_type: str,
    xray_image=None,
    progress=gr.Progress()
) -> str:
    """
    Generate a single Concept B fridge sheet page as HTML.

    Args:
        patient_json: Patient data as JSON string
        page_type: One of 'medications', 'labs', 'care_gaps', 'imaging', 'connections'
        xray_image: Optional uploaded X-ray image for imaging page
        progress: Gradio progress callback

    Returns:
        HTML string for the requested page
    """
    try:
        data = json.loads(patient_json)
    except json.JSONDecodeError as e:
        return f"<html><body><h1>Error: Invalid JSON</h1><pre>{str(e)}</pre></body></html>"

    progress(0.1, desc="Loading MedGemma model...")
    medgemma = get_client()

    # Build PatientInfo
    patient_dict = data.get('patient', {})
    patient = PatientInfo(
        nickname=patient_dict.get('nickname', 'Patient'),
        age_range=patient_dict.get('age_range', ''),
        conditions=patient_dict.get('conditions_display', [])
    )

    def make_progress(current, total, message):
        pct = 0.2 + (0.7 * current / max(total, 1))
        progress(pct, desc=message)

    html = ""

    if page_type == "medications":
        progress(0.2, desc="Generating Medication Schedule...")
        html = generate_medications_page(
            patient=patient,
            medications=data.get('medications', []),
            client=medgemma,
            page_num=1,
            total_pages=5,
            progress_callback=make_progress
        )

    elif page_type == "labs":
        progress(0.2, desc="Generating Lab Results page...")
        html = generate_labs_page(
            patient=patient,
            results=data.get('results', []),
            client=medgemma,
            page_num=2,
            total_pages=5,
            progress_callback=make_progress
        )

    elif page_type == "care_gaps":
        progress(0.2, desc="Generating Care Actions page...")
        html = generate_gaps_page(
            patient=patient,
            care_gaps=data.get('care_gaps', []),
            client=medgemma,
            page_num=3,
            total_pages=5,
            progress_callback=make_progress
        )

    elif page_type == "imaging":
        progress(0.2, desc="Generating Imaging page...")
        image_path = None
        if xray_image is not None:
            image_path = xray_image if isinstance(xray_image, str) else xray_image
        html = generate_imaging_page(
            patient=patient,
            image_path=image_path,
            client=medgemma,
            page_num=4,
            total_pages=5,
            progress_callback=make_progress
        )

    elif page_type == "connections":
        progress(0.2, desc="Generating Connections page...")
        html = generate_connections_page(
            patient=patient,
            medications=data.get('medications', []),
            results=data.get('results', []),
            care_gaps=data.get('care_gaps', []),
            contacts=data.get('contacts', {}),
            page_num=5,
            total_pages=5,
            progress_callback=make_progress
        )

    progress(1.0, desc="Done!")
    return html


def generate_all_concept_b_pages(patient_json: str, xray_image=None, language: str = "english", progress=gr.Progress()):
    """
    Generate all 5 Concept B pages and return them as a tuple.

    When a non-English language is selected, the Medications and Care Actions
    pages are translated using NLLB-200 via the html_translator module.

    Returns:
        Tuple of (medications_html, labs_html, gaps_html, imaging_html, connections_html)
    """
    try:
        data = json.loads(patient_json)
    except json.JSONDecodeError as e:
        error_html = f"<html><body><h1>Error: Invalid JSON</h1><pre>{str(e)}</pre></body></html>"
        return error_html, error_html, error_html, error_html, error_html

    progress(0.05, desc="Loading MedGemma model...")
    medgemma = get_client()

    patient_dict = data.get('patient', {})
    patient = PatientInfo(
        nickname=patient_dict.get('nickname', 'Patient'),
        age_range=patient_dict.get('age_range', ''),
        conditions=patient_dict.get('conditions_display', [])
    )

    # Page 1: Medications
    progress(0.1, desc="[1/5] Generating Medication Schedule...")
    meds_html = generate_medications_page(
        patient=patient,
        medications=data.get('medications', []),
        client=medgemma,
        page_num=1,
        total_pages=5,
        progress_callback=lambda c, t, m: progress(0.1 + (0.15 * c / max(t, 1)), desc=f"[1/5] {m}")
    )

    # Page 2: Labs
    progress(0.3, desc="[2/5] Generating Lab Results...")
    labs_html = generate_labs_page(
        patient=patient,
        results=data.get('results', []),
        client=medgemma,
        page_num=2,
        total_pages=5,
        progress_callback=lambda c, t, m: progress(0.3 + (0.15 * c / max(t, 1)), desc=f"[2/5] {m}")
    )

    # Page 3: Care Gaps
    progress(0.5, desc="[3/5] Generating Care Actions...")
    gaps_html = generate_gaps_page(
        patient=patient,
        care_gaps=data.get('care_gaps', []),
        client=medgemma,
        page_num=3,
        total_pages=5,
        progress_callback=lambda c, t, m: progress(0.5 + (0.15 * c / max(t, 1)), desc=f"[3/5] {m}")
    )

    # Page 4: Imaging
    progress(0.7, desc="[4/5] Generating Imaging page...")
    image_path = xray_image if xray_image else None
    imaging_html = generate_imaging_page(
        patient=patient,
        image_path=image_path,
        client=medgemma,
        page_num=4,
        total_pages=5,
        progress_callback=lambda c, t, m: progress(0.7 + (0.1 * c / max(t, 1)), desc=f"[4/5] {m}")
    )

    # Page 5: Connections
    progress(0.85, desc="[5/5] Generating Connections...")
    connections_html = generate_connections_page(
        patient=patient,
        medications=data.get('medications', []),
        results=data.get('results', []),
        care_gaps=data.get('care_gaps', []),
        contacts=data.get('contacts', {}),
        page_num=5,
        total_pages=5,
        progress_callback=lambda c, t, m: progress(0.85 + (0.1 * c / max(t, 1)), desc=f"[5/5] {m}")
    )

    # Translate Medications and Care Actions pages if non-English
    if language and language != "english":
        target_code = LANGUAGE_CODES.get(language, "eng_Latn")
        if target_code != "eng_Latn":
            progress(0.92, desc=f"Translating Medications to {language}...")
            try:
                trans = get_translator()
                meds_html = translate_fridge_sheet_html(
                    meds_html, trans, target_code,
                    progress_callback=lambda c, t, m: progress(0.92 + (0.03 * c / max(t, 1)), desc=f"Translating Meds ({c}/{t})")
                )
            except Exception as e:
                print(f"Medication translation failed: {e}")

            progress(0.96, desc=f"Translating Care Actions to {language}...")
            try:
                trans = get_translator()
                gaps_html = translate_fridge_sheet_html(
                    gaps_html, trans, target_code,
                    progress_callback=lambda c, t, m: progress(0.96 + (0.03 * c / max(t, 1)), desc=f"Translating Gaps ({c}/{t})")
                )
            except Exception as e:
                print(f"Care gaps translation failed: {e}")

    progress(1.0, desc="All 5 pages generated!")
    return meds_html, labs_html, gaps_html, imaging_html, connections_html


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
) as demo:

    gr.Markdown("""
    # 🏥 CareMap: EHR Enhancement Platform

    **One Model. Three Modules. Better Outcomes.**

    Powered by Google's MedGemma clinical foundation model.

    ---
    """)

    with gr.Tabs():
        # ================================================================
        # TAB 1: PATIENT PORTAL - CONCEPT B FRIDGE SHEETS
        # ================================================================
        with gr.TabItem("👨‍👩‍👧 Patient Portal", id="patient-portal"):
            gr.Markdown("""
            ## 📋 Concept B: Printable Fridge Sheets

            Generate **5 printable 8.5x11" pages** - each designed for a specific audience and purpose.

            | Page | For | Content |
            |------|-----|---------|
            | 💊 Medications | Ayah/Helper | Daily schedule with timing & food instructions |
            | 🔬 Labs | Family | Test results explained in plain language |
            | ✅ Care Actions | Family | Tasks organized: Today / This Week / Coming Up |
            | 🫁 Imaging | Family | X-ray findings with AI interpretation |
            | 🔗 Connections | Both | How meds, labs, and actions work together |
            """)

            with gr.Row():
                with gr.Column(scale=1):
                    input_json = gr.Textbox(label="Patient JSON", lines=15, value=EXAMPLE_PATIENT)
                    xray_upload = gr.Image(label="Upload X-ray (optional, for Imaging page)", type="filepath", height=150)
                    language_dropdown = gr.Dropdown(
                        label="Language (Medications & Care Actions)",
                        choices=LANGUAGE_OPTIONS,
                        value="english",
                        info="Translates Medication Schedule and Care Actions pages using NLLB-200"
                    )
                    generate_all_btn = gr.Button("🖨️ Generate All 5 Pages", variant="primary", size="lg")

                with gr.Column(scale=2):
                    with gr.Tabs() as page_tabs:
                        with gr.TabItem("💊 Medications", id="tab-meds"):
                            meds_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Click 'Generate All 5 Pages' to create the Medication Schedule</p>")
                        with gr.TabItem("🔬 Labs", id="tab-labs"):
                            labs_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Click 'Generate All 5 Pages' to create Lab Results</p>")
                        with gr.TabItem("✅ Care Actions", id="tab-gaps"):
                            gaps_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Click 'Generate All 5 Pages' to create Care Actions</p>")
                        with gr.TabItem("🫁 Imaging", id="tab-imaging"):
                            imaging_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Click 'Generate All 5 Pages' to create Imaging page</p>")
                        with gr.TabItem("🔗 Connections", id="tab-connections"):
                            connections_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Click 'Generate All 5 Pages' to create Connections</p>")

            generate_all_btn.click(
                fn=generate_all_concept_b_pages,
                inputs=[input_json, xray_upload, language_dropdown],
                outputs=[meds_output, labs_output, gaps_output, imaging_output, connections_output],
            )

            gr.Markdown("""
            ---
            ### 🖨️ How to Print
            1. Click on a page tab above
            2. Right-click the page → "Print" or use Ctrl/Cmd+P
            3. Select "Save as PDF" or print directly
            4. Each page is designed for 8.5x11" paper
            """)

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
    demo.launch(theme=gr.themes.Soft())
