"""
CareMap: AI-Powered Caregiver Fridge Sheet
HuggingFace Spaces Gradio App

Converts patient health data into a single-page caregiver aid.
Supports multiple languages via NLLB-200 translation.
"""

import json
import gradio as gr
from pathlib import Path

# Import CareMap modules
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from caremap.llm_client import MedGemmaClient
from caremap.lab_interpretation import interpret_lab
from caremap.medication_interpretation import interpret_medication_v3_grounded
from caremap.imaging_interpretation import interpret_imaging_report
from caremap.caregap_interpretation import interpret_caregap
from caremap.translation import (
    NLLBTranslator,
    LANGUAGE_CODES,
    LANGUAGE_NAMES,
)


# Global clients (loaded once)
medgemma_client = None
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
    """Lazy load the MedGemma client."""
    global medgemma_client
    if medgemma_client is None:
        print("Loading MedGemma model...")
        medgemma_client = MedGemmaClient()
        print("MedGemma loaded!")
    return medgemma_client


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


# Example patient data
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


def generate_fridge_sheet(patient_json: str, language: str = "english", progress=gr.Progress()) -> str:
    """
    Generate a caregiver fridge sheet from patient JSON data.

    Args:
        patient_json: JSON string with patient data
        language: Target language for output
        progress: Gradio progress tracker

    Returns:
        Markdown formatted fridge sheet
    """
    try:
        # Parse JSON
        data = json.loads(patient_json)
    except json.JSONDecodeError as e:
        return f"**Error:** Invalid JSON\n\n```\n{str(e)}\n```"

    # Get client
    progress(0.1, desc="Loading model...")
    medgemma = get_client()

    # Get target language name for display
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

    # Build fridge sheet
    lines = []

    # Header
    nickname = patient.get('nickname', 'Patient')
    age = patient.get('age_range', '')
    conditions = patient.get('conditions_display', [])

    lines.append(f"# CareMap Fridge Sheet: {nickname}")
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

        # Group by urgency
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
            except Exception:
                action = gap.get('item_text', '')

            bucket = gap.get('time_bucket', 'This Week')
            if bucket == 'Today':
                today_items.append(action)
            else:
                week_items.append(action)

        if today_items:
            lines.append("## Today's Priorities")
            for item in today_items:
                lines.append(f"- [ ] **{item}**")
            lines.append("")

        if week_items:
            lines.append("## This Week")
            for item in week_items:
                lines.append(f"- [ ] {item}")
            lines.append("")

    # Medications
    if medications:
        progress(0.4, desc="Processing medications...")
        lines.append("## Medications")

        for i, med in enumerate(medications[:5]):  # Limit to 5 for speed
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
                what_it_does = result.get('what_it_does', '')[:150]
                if 'raw_response' in result:
                    what_it_does = ''
            except Exception:
                what_it_does = ''

            lines.append(f"**{name}** ({timing})")
            if what_it_does:
                lines.append(f"- {what_it_does}")
            lines.append("")

    # Labs
    if results:
        progress(0.7, desc="Processing lab results...")
        lines.append("## Recent Labs")

        for i, lab in enumerate(results[:4]):  # Limit to 4
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
                # Get first sentence only
                meaning = meaning.split('.')[0] + '.' if meaning else category
            except Exception:
                meaning = category

            lines.append(f"- **{name}**: {meaning}")
        lines.append("")

    # Contacts
    if contacts:
        lines.append("## Contacts")
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

    # Combine into markdown
    english_output = "\n".join(lines)

    # Translate if not English
    if language != "english":
        progress(0.95, desc=f"Translating to {language}...")
        try:
            # Translate each section (preserving markdown structure)
            translated_lines = []
            for line in lines:
                if line.startswith("#") or line.startswith("---") or line == "":
                    # Keep headers and separators, translate header text
                    if line.startswith("# "):
                        translated_lines.append("# " + translate_text(line[2:], language))
                    elif line.startswith("## "):
                        translated_lines.append("## " + translate_text(line[3:], language))
                    else:
                        translated_lines.append(line)
                elif line.startswith("- "):
                    # Translate list items
                    translated_lines.append("- " + translate_text(line[2:], language))
                elif line.startswith("**"):
                    # Translate bold text lines
                    translated_lines.append(translate_text(line, language))
                elif line.startswith("*"):
                    # Translate italic footer
                    translated_lines.append("*" + translate_text(line.strip("*"), language) + "*")
                else:
                    translated_lines.append(translate_text(line, language))

            output = "\n".join(translated_lines)
        except Exception as e:
            # Fallback to English if translation fails
            output = english_output + f"\n\n*(Translation to {language} failed: {str(e)})*"
    else:
        output = english_output

    progress(1.0, desc="Done!")

    return output


# Create Gradio interface
with gr.Blocks(
    title="CareMap: Caregiver Fridge Sheet",
    theme=gr.themes.Soft(),
) as demo:

    gr.Markdown("""
    # CareMap: AI-Powered Caregiver Fridge Sheet

    Transform complex patient data into a simple, one-page caregiver aid.

    **How to use:**
    1. Paste patient JSON data in the left panel (or use the example)
    2. Select output language (supports 10 languages!)
    3. Click "Generate Fridge Sheet"
    4. View the formatted output on the right

    **Safety:** CareMap provides information only - no diagnoses, no dosage advice, no treatment changes.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Patient Data (JSON)")
            input_json = gr.Textbox(
                label="Patient JSON",
                placeholder="Paste patient JSON here...",
                lines=20,
                value=EXAMPLE_PATIENT,
            )

            gr.Markdown("### Output Language")
            language_dropdown = gr.Dropdown(
                label="Select Language",
                choices=[label for label, _ in LANGUAGE_OPTIONS],
                value="English",
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

    # Map display name to language code
    def get_lang_code(display_name):
        for label, code in LANGUAGE_OPTIONS:
            if label == display_name:
                return code
        return "english"

    # Event handlers
    generate_btn.click(
        fn=lambda json_str, lang: generate_fridge_sheet(json_str, get_lang_code(lang)),
        inputs=[input_json, language_dropdown],
        outputs=[output_md],
    )

    clear_btn.click(
        fn=lambda: ("", "English", "*Click 'Generate Fridge Sheet' to see output*"),
        outputs=[input_json, language_dropdown, output_md],
    )

    gr.Markdown("""
    ---

    **About CareMap**

    Built for the [MedGemma Impact Challenge](https://www.kaggle.com/competitions/medgemma-impact-challenge).
    Uses MedGemma 4B for plain-language medical explanations.

    [GitHub Repository](https://github.com/YOUR_USERNAME/caremap-medgemma) |
    [Kaggle Notebook](https://www.kaggle.com/YOUR_USERNAME/caremap)
    """)


if __name__ == "__main__":
    demo.launch()
