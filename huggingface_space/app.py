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

# Import CareMap modules — GPU-dependent imports are conditional
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

GPU_AVAILABLE = False
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    pass

if GPU_AVAILABLE:
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


if GPU_AVAILABLE:
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


AMMA_PATIENT = '''{
  "patient": {
    "nickname": "Amma",
    "age_range": "70s",
    "conditions_display": [
      "Alzheimer's disease",
      "Diabetes",
      "Hypertension",
      "Hyperlipidemia",
      "Acute Anemia"
    ]
  },
  "medications": [
    {
      "medication_name": "Donepezil",
      "sig_text": "Take 1 tablet by mouth daily at bedtime",
      "timing": "at bedtime",
      "clinician_notes": "For Alzheimer's cognitive support. Monitor for nausea or vivid dreams.",
      "interaction_notes": ""
    },
    {
      "medication_name": "Memantine",
      "sig_text": "Take 1 tablet by mouth twice daily",
      "timing": "morning and evening",
      "clinician_notes": "Added for moderate Alzheimer's. Works with Donepezil.",
      "interaction_notes": ""
    },
    {
      "medication_name": "Metformin",
      "sig_text": "Take 1 tablet by mouth twice daily with meals",
      "timing": "morning and evening, with food",
      "clinician_notes": "Monitor kidney function every 6 months.",
      "interaction_notes": "Take with food to reduce stomach upset. Hold 48 hours before and after any CT scan with contrast dye."
    },
    {
      "medication_name": "Glimepiride",
      "sig_text": "Take 1 tablet by mouth daily with breakfast",
      "timing": "morning, with breakfast",
      "clinician_notes": "Added because Metformin alone was not controlling blood sugar.",
      "interaction_notes": "Can cause low blood sugar. Keep glucose tablets or juice nearby. Do not skip meals."
    },
    {
      "medication_name": "Amlodipine",
      "sig_text": "Take 1 tablet by mouth daily in the morning",
      "timing": "morning",
      "clinician_notes": "For blood pressure control.",
      "interaction_notes": "May cause ankle swelling. Rise slowly from sitting to avoid dizziness."
    },
    {
      "medication_name": "Losartan",
      "sig_text": "Take 1 tablet by mouth daily",
      "timing": "morning",
      "clinician_notes": "Added for blood pressure and kidney protection with diabetes.",
      "interaction_notes": "Can raise potassium levels. Avoid potassium-rich salt substitutes."
    },
    {
      "medication_name": "Atorvastatin",
      "sig_text": "Take 1 tablet by mouth daily at bedtime",
      "timing": "at bedtime",
      "clinician_notes": "For cholesterol control. Check liver function yearly.",
      "interaction_notes": "Avoid grapefruit juice. Report any unexplained muscle pain."
    },
    {
      "medication_name": "Ferrous Sulfate",
      "sig_text": "Take 1 tablet by mouth daily on empty stomach",
      "timing": "morning, 1 hour before breakfast",
      "clinician_notes": "For iron deficiency anemia. Recheck hemoglobin in 3 months.",
      "interaction_notes": "Take on empty stomach with orange juice for better absorption. Separate from calcium, antacids, and Metformin by at least 2 hours. May cause constipation or dark stools."
    }
  ],
  "results": [
    {
      "test_name": "Hemoglobin",
      "meaning_category": "Needs follow-up",
      "source_note": "Below normal — iron deficiency anemia being treated"
    },
    {
      "test_name": "Ferritin (Iron Stores)",
      "meaning_category": "Needs follow-up",
      "source_note": "Low iron stores — continue iron supplement"
    },
    {
      "test_name": "Hemoglobin A1c (3-Month Blood Sugar Average)",
      "meaning_category": "Needs follow-up",
      "source_note": "Above target — Glimepiride added at last visit"
    },
    {
      "test_name": "Fasting Blood Sugar",
      "meaning_category": "Slightly off",
      "source_note": "Slightly above goal — monitor with new medication"
    },
    {
      "test_name": "Total Cholesterol",
      "meaning_category": "Slightly off",
      "source_note": "Above target despite Atorvastatin — discuss diet at next visit"
    },
    {
      "test_name": "Kidney Function (eGFR)",
      "meaning_category": "Normal",
      "source_note": "Stable — safe to continue Metformin"
    },
    {
      "test_name": "Potassium Level",
      "meaning_category": "Normal",
      "source_note": "Within normal range — monitoring due to Losartan"
    }
  ],
  "care_gaps": [
    {
      "item_text": "Blood sugar log review — bring log to next visit",
      "next_step": "Record fasting blood sugar daily",
      "time_bucket": "Today"
    },
    {
      "item_text": "Annual flu shot not received",
      "next_step": "Ask pharmacy about flu shot availability",
      "time_bucket": "Today"
    },
    {
      "item_text": "Diabetic eye exam overdue",
      "next_step": "Schedule appointment with eye doctor",
      "time_bucket": "This Week"
    },
    {
      "item_text": "Neurology follow-up for Alzheimer's medication review",
      "next_step": "Call neurologist to schedule 6-month check",
      "time_bucket": "This Week"
    },
    {
      "item_text": "Hemoglobin recheck due in 3 months to track anemia treatment",
      "next_step": "Schedule lab for April",
      "time_bucket": "Later"
    }
  ],
  "contacts": {
    "clinic_name": "Kolkata Family Medicine",
    "clinic_phone": "033-2555-0100",
    "pharmacy_name": "Apollo Pharmacy",
    "pharmacy_phone": "033-2555-0200"
  }
}'''


PATIENT_CHOICES = {
    "Dadu — Complex Cardiac (80s M)": {"json": EXAMPLE_PATIENT, "dir": "dadu"},
    "Amma — Alzheimer's & Anemia (70s F)": {"json": AMMA_PATIENT, "dir": "amma"},
}

STATIC_DIR = Path(__file__).parent / "static"

STATIC_BANNER = '''<div style="background:#f0f7ff; border:1px solid #b3d4fc;
  border-radius:8px; padding:12px 16px; margin:12px 0; font-size:14px; color:#1a56db;">
  &#x2139;&#xfe0f; These pages were pre-generated on a Kaggle T4 GPU for demonstration purposes.
  Click "Regenerate with MedGemma" below to generate live output (requires GPU).
</div>'''


BENGALI_BANNER = '''<div style="background:#fff3e0; border:1px solid #ffcc80;
  border-radius:8px; padding:12px 16px; margin:12px 0; font-size:14px; color:#e65100;">
  &#x1F30F; Bengali (&#x09AC;&#x09BE;&#x0982;&#x09B2&#x09BE;) translation generated by NLLB-200 on Kaggle T4 GPU.
  Medication names are preserved in English for safety.
</div>'''


def load_static_demo(patient_label):
    """Load pre-generated HTML for selected patient."""
    choice = PATIENT_CHOICES.get(patient_label)
    if not choice:
        return ("",) * 8 + (EXAMPLE_PATIENT,)

    summary_html = generate_patient_summary_html(choice["json"])

    patient_dir = STATIC_DIR / choice["dir"]
    pages = []
    for filename in [
        "1_medications.html",
        "2_labs.html",
        "3_care_gaps.html",
        "4_imaging.html",
        "5_connections.html",
    ]:
        filepath = patient_dir / filename
        if filepath.exists():
            html = filepath.read_text()
            pages.append(STATIC_BANNER + html)
        else:
            pages.append(
                "<p style='padding:2rem; color:#999;'>Pre-generated HTML not yet available. "
                "Run the Kaggle notebook to generate.</p>"
            )

    # Bengali translated pages
    bengali_pages = []
    for filename in ["1_medications_bn.html", "3_care_gaps_bn.html"]:
        filepath = patient_dir / filename
        if filepath.exists():
            html = filepath.read_text()
            bengali_pages.append(BENGALI_BANNER + html)
        else:
            bengali_pages.append(
                "<p style='padding:2rem; color:#999;'>Bengali translation not yet available. "
                "Run the Kaggle notebook to generate.</p>"
            )

    return (summary_html,) + tuple(pages) + tuple(bengali_pages) + (choice["json"],)


def generate_patient_summary_html(json_str):
    """Generate a clean HTML summary of the raw patient EHR data (input view)."""
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return "<p style='padding:2rem; color:#999;'>Invalid or empty patient JSON.</p>"

    patient = data.get("patient", {})
    nickname = patient.get("nickname", "Patient")
    age_range = patient.get("age_range", "")
    conditions = patient.get("conditions_display", [])
    medications = data.get("medications", [])
    results = data.get("results", [])
    care_gaps = data.get("care_gaps", [])
    contacts = data.get("contacts", {})

    # Condition badge colors
    badge_colors = ["#e3f2fd", "#fce4ec", "#f3e5f5", "#e8f5e9", "#fff3e0", "#e0f7fa", "#fbe9e7"]

    conditions_html = ""
    for i, c in enumerate(conditions):
        bg = badge_colors[i % len(badge_colors)]
        conditions_html += (
            f'<span style="display:inline-block; background:{bg}; border-radius:12px; '
            f'padding:4px 12px; margin:2px 4px; font-size:13px;">{c}</span>'
        )

    # Medications table
    meds_rows = ""
    for med in medications:
        name = med.get("medication_name", "")
        sig = med.get("sig_text", "")
        timing = med.get("timing", "")
        clin = med.get("clinician_notes", "")
        interact = med.get("interaction_notes", "")
        meds_rows += (
            f"<tr><td style='font-weight:600;'>{name}</td>"
            f"<td>{sig}</td><td>{timing}</td>"
            f"<td style='font-size:12px;'>{clin}</td>"
            f"<td style='font-size:12px; color:#c62828;'>{interact}</td></tr>"
        )

    # Lab results table
    flag_colors = {
        "Normal": ("#2e7d32", "#e8f5e9"),
        "Slightly off": ("#f57f17", "#fff8e1"),
        "Needs follow-up": ("#c62828", "#ffebee"),
    }
    labs_rows = ""
    for lab in results:
        name = lab.get("test_name", "")
        cat = lab.get("meaning_category", "Normal")
        note = lab.get("source_note", "")
        fg, bg = flag_colors.get(cat, ("#333", "#f5f5f5"))
        labs_rows += (
            f"<tr><td>{name}</td>"
            f'<td style="background:{bg}; color:{fg}; font-weight:600; text-align:center; border-radius:4px;">{cat}</td>'
            f"<td style='font-size:12px;'>{note}</td></tr>"
        )

    # Care gaps grouped by bucket
    buckets = {"Today": [], "This Week": [], "Later": []}
    for gap in care_gaps:
        bucket = gap.get("time_bucket", "This Week")
        buckets.setdefault(bucket, []).append(gap)

    bucket_icons = {"Today": "🚨", "This Week": "📅", "Later": "📌"}
    gaps_html = ""
    for bucket_name in ["Today", "This Week", "Later"]:
        items = buckets.get(bucket_name, [])
        if not items:
            continue
        gaps_html += f"<h4 style='margin:12px 0 6px;'>{bucket_icons.get(bucket_name, '')} {bucket_name}</h4><ul style='margin:0;'>"
        for gap in items:
            gaps_html += f"<li><strong>{gap.get('item_text', '')}</strong> &rarr; {gap.get('next_step', '')}</li>"
        gaps_html += "</ul>"

    # Contacts
    contacts_html = ""
    if contacts.get("clinic_name"):
        contacts_html += f"<p>🏥 <strong>{contacts['clinic_name']}</strong> &mdash; {contacts.get('clinic_phone', '')}</p>"
    if contacts.get("pharmacy_name"):
        contacts_html += f"<p>💊 <strong>{contacts['pharmacy_name']}</strong> &mdash; {contacts.get('pharmacy_phone', '')}</p>"

    html = f"""
    <div style="font-family: 'Inter', -apple-system, sans-serif; max-width:900px; margin:0 auto; padding:16px;">
      <div style="background:linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%); border-radius:12px; padding:20px 24px; margin-bottom:20px;">
        <h2 style="margin:0 0 8px;">📋 {nickname}'s Health Record</h2>
        <p style="margin:0 0 8px; color:#555;">Age range: <strong>{age_range}</strong></p>
        <div>{conditions_html}</div>
      </div>

      <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:16px;">
        <h3 style="margin:0 0 12px;">💊 Medications ({len(medications)})</h3>
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
              <tr style="background:#f5f5f5; text-align:left;">
                <th style="padding:8px; border-bottom:2px solid #ddd;">Name</th>
                <th style="padding:8px; border-bottom:2px solid #ddd;">Directions</th>
                <th style="padding:8px; border-bottom:2px solid #ddd;">Timing</th>
                <th style="padding:8px; border-bottom:2px solid #ddd;">Clinician Notes</th>
                <th style="padding:8px; border-bottom:2px solid #ddd;">Interactions</th>
              </tr>
            </thead>
            <tbody>
              {meds_rows}
            </tbody>
          </table>
        </div>
      </div>

      <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:16px;">
        <h3 style="margin:0 0 12px;">🔬 Lab Results ({len(results)})</h3>
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
              <tr style="background:#f5f5f5; text-align:left;">
                <th style="padding:8px; border-bottom:2px solid #ddd;">Test</th>
                <th style="padding:8px; border-bottom:2px solid #ddd; width:130px;">Status</th>
                <th style="padding:8px; border-bottom:2px solid #ddd;">Source Note</th>
              </tr>
            </thead>
            <tbody>
              {labs_rows}
            </tbody>
          </table>
        </div>
      </div>

      <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:16px;">
        <h3 style="margin:0 0 8px;">✅ Care Gaps ({len(care_gaps)})</h3>
        {gaps_html}
      </div>

      <div style="background:#fff; border:1px solid #e0e0e0; border-radius:8px; padding:16px; margin-bottom:16px;">
        <h3 style="margin:0 0 8px;">📞 Contacts</h3>
        {contacts_html if contacts_html else "<p style='color:#999;'>No contacts listed.</p>"}
      </div>

      <p style="text-align:center; color:#999; font-size:12px; margin-top:16px;">
        This is the <strong>raw EHR input data</strong>. The tabs to the right show what MedGemma generates from it.
      </p>
    </div>
    """
    return html


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

# Pre-generated demo results for CPU-only mode
DEMO_HL7_BATCH_RESULT = """# 🏥 HL7 ORU Triage Queue

**6 Messages Analyzed** | 🔴 3 STAT | 🟡 1 SOON | 🟢 2 ROUTINE

---

## 🔴 STAT - Critical (Intervene now)
**ORU-001** | LAB | 67M | 95%
- Potassium 6.8 mEq/L — critically elevated, risk of cardiac arrhythmia. Hold ACE inhibitor and K+-sparing diuretic...

**ORU-002** | LAB | 45F | 97%
- Troponin I 2.45 ng/mL (ref <0.04) — highly elevated, consistent with acute myocardial infarction...

**ORU-005** | RADIOLOGY | 58M | 93%
- Large left-sided pneumothorax with mediastinal shift — tension pneumothorax, emergent decompression required...

## 🟡 SOON - Abnormal (Review < 1 hour)
**ORU-003** | LAB | 55M | 88%
- INR 4.2 (target 2.0-3.0) — supratherapeutic anticoagulation, increased bleeding risk. Hold warfarin dose...

## 🟢 ROUTINE - Normal (Review < 24 hours)
**ORU-004** | LAB | 42F | 92%
- All values within normal limits. Fasting glucose 92, cholesterol 195 — no action needed...

**ORU-006** | LAB | 35M | 95%
- CBC within normal limits. WBC 7.2, Hgb 14.5, Plt 245 — cleared for employment physical...

---
⚠️ **Important:** AI prioritizes the message queue. Clinicians review ALL results.

*Pre-generated with MedGemma 1.5 4B-IT on Kaggle T4 GPU*
"""

DEMO_HL7_SINGLE_RESULTS = {
    "ORU-001": """# 🔴 HL7 Triage Result: STAT

## Message: ORU-001
**Type:** LAB | **Patient:** 67 M

## Priority Reason
Potassium 6.8 mEq/L is critically elevated (ref 3.5-5.0). This level poses immediate risk of fatal cardiac arrhythmia. Patient is on ACE inhibitor and potassium-sparing diuretic, which are likely contributing factors.

## Key Findings
- Critical hyperkalemia: K+ 6.8 mEq/L (HH flag)
- Drug interaction risk: ACE inhibitor + K+-sparing diuretic
- Immediate cardiac monitoring needed

## Recommended Action
STAT ECG, continuous cardiac monitoring. Hold ACE inhibitor and potassium-sparing diuretic. Consider IV calcium gluconate, insulin/glucose, and kayexalate. Notify attending physician immediately.

## AI Confidence
95%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
    "ORU-002": """# 🔴 HL7 Triage Result: STAT

## Message: ORU-002
**Type:** LAB | **Patient:** 45 F

## Priority Reason
Troponin I 2.45 ng/mL is markedly elevated (ref <0.04), strongly suggestive of acute myocardial injury. CK-MB 45 U/L (ref 0-25) further supports diagnosis. In context of chest pain, this is consistent with acute MI.

## Key Findings
- Troponin I critically elevated at 2.45 ng/mL (>60x upper limit)
- CK-MB elevated at 45 U/L (1.8x upper limit)
- Clinical presentation: chest pain — rule out MI

## Recommended Action
Activate STEMI/NSTEMI protocol. STAT 12-lead ECG, serial troponins q3h. Cardiology consult. Heparin drip, dual antiplatelet therapy per protocol. Consider emergent cardiac catheterization.

## AI Confidence
97%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
    "ORU-003": """# 🟡 HL7 Triage Result: SOON

## Message: ORU-003
**Type:** LAB | **Patient:** 55 M

## Priority Reason
INR 4.2 is above therapeutic range (target 2.0-3.0) for AFib patient on warfarin. Elevated bleeding risk but no evidence of active bleeding described.

## Key Findings
- INR 4.2 — supratherapeutic (target 2.0-3.0)
- Patient on warfarin for AFib
- No reported bleeding symptoms

## Recommended Action
Hold warfarin 1-2 doses. Recheck INR in 24-48 hours. Assess for signs of bleeding. Adjust warfarin dose when INR returns to range. No vitamin K needed unless active bleeding.

## AI Confidence
88%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
    "ORU-004": """# 🟢 HL7 Triage Result: ROUTINE

## Message: ORU-004
**Type:** LAB | **Patient:** 42 F

## Priority Reason
All laboratory values within normal reference ranges. Annual wellness exam results are reassuring.

## Key Findings
- Fasting glucose 92 mg/dL (ref 70-100) — normal
- Total cholesterol 195 mg/dL (ref <200) — normal

## Recommended Action
File results. No urgent follow-up needed. Results can be reviewed at next scheduled visit.

## AI Confidence
92%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
    "ORU-005": """# 🔴 HL7 Triage Result: STAT

## Message: ORU-005
**Type:** RADIOLOGY | **Patient:** 58 M

## Priority Reason
Large left-sided pneumothorax with complete lung collapse and mediastinal shift indicates tension pneumothorax — a life-threatening emergency requiring immediate intervention.

## Key Findings
- Complete collapse of left lung
- Mediastinal shift to the right (tension pneumothorax)
- Clinical context: sudden onset dyspnea and chest pain

## Recommended Action
Emergent needle decompression followed by chest tube insertion. This is a surgical emergency. Notify thoracic surgery and attending physician immediately.

## AI Confidence
93%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
    "ORU-006": """# 🟢 HL7 Triage Result: ROUTINE

## Message: ORU-006
**Type:** LAB | **Patient:** 35 M

## Priority Reason
Complete blood count within normal limits. Pre-employment physical results are unremarkable.

## Key Findings
- WBC 7.2 (ref 4.5-11.0) — normal
- Hemoglobin 14.5 g/dL (ref 13.5-17.5) — normal
- Platelet count 245 (ref 150-400) — normal

## Recommended Action
File results. Patient cleared from hematologic standpoint for employment physical.

## AI Confidence
95%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All results MUST be reviewed by a clinician.
""",
}

DEMO_RADIOLOGY_RESULT = """# 🔴 Triage Result: STAT

## Priority Level
**STAT** - Large left-sided pneumothorax with tension physiology requiring emergent intervention

## Findings
- Complete opacification/absence of lung markings in left hemithorax
- Mediastinal shift to the right
- Deep sulcus sign
- Flattened left hemidiaphragm
- Tracheal deviation to the right

## Primary Impression
Tension pneumothorax, left-sided, with complete lung collapse and mediastinal shift.

## AI Confidence
95%

---
⚠️ **Disclaimer:** AI-assisted triage for prioritization only. All images MUST be reviewed by a radiologist.

*Pre-generated with MedGemma 1.5 4B-IT (multimodal) on Kaggle T4 GPU*
"""


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
- STAT: Critical findings requiring immediate intervention (intervene now)
- SOON: Abnormal findings requiring urgent review (< 1 hour)
- ROUTINE: Normal or minor findings (< 24 hours)

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
- STAT: Life-threatening or critical values (intervene now) - e.g., K+ >6.5, troponin elevation, severe anemia
- SOON: Abnormal results requiring urgent review (< 1 hour) - e.g., elevated INR, worsening renal
- ROUTINE: Normal results or minor abnormalities (< 24 hours)

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

## 🔴 STAT - Critical (Intervene now)
"""
    for r in stat:
        output += f"**{r['message_id']}** | {r['message_type']} | {r['patient']} | {r['confidence']:.0%}\n"
        output += f"- {r['reason'][:80]}...\n\n"

    output += "\n## 🟡 SOON - Abnormal (Review < 1 hour)\n"
    for r in soon:
        output += f"**{r['message_id']}** | {r['message_type']} | {r['patient']} | {r['confidence']:.0%}\n"
        output += f"- {r['reason'][:80]}...\n\n"

    output += "\n## 🟢 ROUTINE - Normal (Review < 24 hours)\n"
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

PRINT_CSS = """
@media print {
    /* Hide everything by default */
    body * { visibility: hidden; height: 0; overflow: hidden; }

    /* Keep the container chain visible so the printable sheet can render */
    body, .gradio-container, .gradio-container > *,
    .tabs, .tabitem, .tab-content {
        visibility: visible !important;
        height: auto !important;
        overflow: visible !important;
    }

    /* Show only the printable sheet content */
    .printable-sheet, .printable-sheet * {
        visibility: visible !important;
        height: auto !important;
        overflow: visible !important;
    }

    /* Position printable content at top, full width */
    .printable-sheet {
        position: absolute;
        left: 0; top: 0;
        width: 100%;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Remove Gradio container constraints */
    .gradio-container {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Hide tab navigation bar, buttons, dropdowns */
    .tab-nav, button, select, .gradio-dropdown,
    .gradio-button, .gradio-image, .gradio-textbox,
    .gradio-accordion, footer, nav {
        display: none !important;
    }
}
"""

with gr.Blocks(
    title="CareMap: EHR Enhancement Platform",
    css=PRINT_CSS,
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
            with gr.Row():
                with gr.Column(scale=3):
                    gr.Markdown("""
                    ## Caregiver Fridge Sheets

                    MedGemma transforms complex EHR data into **printable 8.5x11" pages** that caregivers can post on the fridge.

                    | Page | For | Content |
                    |------|-----|---------|
                    | 📋 Patient Data | Judges/Devs | Raw EHR input — what MedGemma receives |
                    | 💊 Medications | Ayah/Helper | Daily schedule with timing & food instructions |
                    | 🔬 Labs | Family | Test results explained in plain language |
                    | ✅ Care Actions | Family | Tasks organized: Today / This Week / Coming Up |
                    | 🫁 Imaging | Family | X-ray findings with AI interpretation |
                    | 🔗 Connections | Both | How meds, labs, and actions work together |
                    | 🌏 Meds (বাংলা) | Ayah | Bengali medication schedule via NLLB-200 |
                    | 🌏 Actions (বাংলা) | Ayah | Bengali care actions via NLLB-200 |
                    """)
                with gr.Column(scale=2):
                    patient_dropdown = gr.Dropdown(
                        label="Select Patient",
                        choices=list(PATIENT_CHOICES.keys()),
                        value=list(PATIENT_CHOICES.keys())[0],
                        info="Choose a patient to view pre-generated fridge sheets"
                    )
                    with gr.Accordion("Patient JSON (editable)", open=False):
                        input_json = gr.Textbox(label="Patient JSON", lines=15, value=EXAMPLE_PATIENT)
                    xray_upload = gr.Image(label="Upload X-ray (optional, for Imaging page)", type="filepath", height=150)
                    language_dropdown = gr.Dropdown(
                        label="Language (Medications & Care Actions)",
                        choices=LANGUAGE_OPTIONS,
                        value="english",
                        info="Translates Medication Schedule and Care Actions pages using NLLB-200"
                    )
                    generate_all_btn = gr.Button("Regenerate with MedGemma (requires GPU)", variant="secondary", size="lg")

            with gr.Tabs() as page_tabs:
                with gr.TabItem("📋 Patient Data", id="tab-summary"):
                    summary_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view their health record</p>", elem_classes="printable-sheet")
                with gr.TabItem("💊 Medications", id="tab-meds"):
                    meds_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view pre-generated pages</p>", elem_classes="printable-sheet")
                with gr.TabItem("🔬 Labs", id="tab-labs"):
                    labs_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view pre-generated pages</p>", elem_classes="printable-sheet")
                with gr.TabItem("✅ Care Actions", id="tab-gaps"):
                    gaps_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view pre-generated pages</p>", elem_classes="printable-sheet")
                with gr.TabItem("🫁 Imaging", id="tab-imaging"):
                    imaging_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view pre-generated pages</p>", elem_classes="printable-sheet")
                with gr.TabItem("🔗 Connections", id="tab-connections"):
                    connections_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view pre-generated pages</p>", elem_classes="printable-sheet")
                with gr.TabItem("🌏 Meds (বাংলা)", id="tab-meds-bn"):
                    meds_bn_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view Bengali translation</p>", elem_classes="printable-sheet")
                with gr.TabItem("🌏 Actions (বাংলা)", id="tab-gaps-bn"):
                    gaps_bn_output = gr.HTML(value="<p style='padding:2rem; color:#666;'>Select a patient to view Bengali translation</p>", elem_classes="printable-sheet")

            # Wire dropdown to load static demo pages + update JSON textbox
            patient_dropdown.change(
                fn=load_static_demo,
                inputs=[patient_dropdown],
                outputs=[summary_output, meds_output, labs_output, gaps_output, imaging_output, connections_output, meds_bn_output, gaps_bn_output, input_json],
            )

            # Wire regenerate button to generate live with MedGemma
            generate_all_btn.click(
                fn=generate_all_concept_b_pages,
                inputs=[input_json, xray_upload, language_dropdown],
                outputs=[meds_output, labs_output, gaps_output, imaging_output, connections_output],
            )

            # Load static demo on page load
            demo.load(
                fn=load_static_demo,
                inputs=[patient_dropdown],
                outputs=[summary_output, meds_output, labs_output, gaps_output, imaging_output, connections_output, meds_bn_output, gaps_bn_output, input_json],
            )

            gr.Markdown("""
            ---
            ### 🖨️ How to Print
            1. Click on a page tab above
            2. Press **Ctrl+P** (Windows) or **Cmd+P** (Mac)
            3. Only the fridge sheet content will print — Gradio controls are hidden automatically
            4. Each page is designed for 8.5×11" paper
            """)

        # ================================================================
        # TAB 2: RADIOLOGY TRIAGE
        # ================================================================
        with gr.TabItem("🔬 Radiology Triage", id="radiology-triage"):
            gr.Markdown("""
            ## AI-Assisted Radiology Triage (Multimodal)

            MedGemma analyzes chest X-rays and prioritizes the review queue.

            🔴 **STAT** Intervene now | 🟡 **SOON** < 1 hour | 🟢 **ROUTINE** < 24 hours
            """)

            if GPU_AVAILABLE:
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
            else:
                gr.Markdown("""
                > **Demo Mode (CPU):** Live X-ray analysis requires GPU + MedGemma multimodal.
                > Below is a pre-generated example from a Kaggle T4 GPU run.
                """)
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Sample Chest X-ray")
                        gr.Markdown("*NIH Clinical Center ChestX-ray14 dataset — Patient 00000032*")
                        gr.Image(value="static/demo_xray/stat_xray.png", label="Chest X-ray (STAT case)", height=400, interactive=False)
                    with gr.Column(scale=1):
                        gr.Markdown("### MedGemma Triage Result")
                        gr.Markdown(DEMO_RADIOLOGY_RESULT)

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

            if GPU_AVAILABLE:
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
            else:
                gr.Markdown("""
                > **Demo Mode (CPU):** Live HL7 triage requires GPU + MedGemma.
                > Below are pre-generated results from a Kaggle T4 GPU run.
                """)

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Select a Message")
                        demo_msg_dropdown = gr.Dropdown(
                            label="Sample HL7 Messages",
                            choices=[f"{m['message_id']} - {m['message_type']} - {m['clinical_context'][:40]}..." for m in EXAMPLE_HL7_MESSAGES],
                            value=f"{EXAMPLE_HL7_MESSAGES[0]['message_id']} - {EXAMPLE_HL7_MESSAGES[0]['message_type']} - {EXAMPLE_HL7_MESSAGES[0]['clinical_context'][:40]}..."
                        )
                        demo_single_btn = gr.Button("View Triage Result", variant="primary", size="lg")
                        gr.Markdown("---")
                        demo_batch_btn = gr.Button("View All 6 Results", variant="secondary", size="lg")

                    with gr.Column(scale=1):
                        gr.Markdown("### Triage Results")
                        demo_hl7_output = gr.Markdown(value=DEMO_HL7_SINGLE_RESULTS["ORU-001"])

                def demo_triage_selected(selection):
                    msg_id = selection.split(" - ")[0]
                    return DEMO_HL7_SINGLE_RESULTS.get(msg_id, "Message not found")

                def demo_triage_batch():
                    return DEMO_HL7_BATCH_RESULT

                demo_single_btn.click(fn=demo_triage_selected, inputs=[demo_msg_dropdown], outputs=[demo_hl7_output])
                demo_batch_btn.click(fn=demo_triage_batch, outputs=[demo_hl7_output])

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

    Built for [Kaggle MedGemma Impact Challenge](https://www.kaggle.com/competitions/med-gemma-impact-challenge) |
    Powered by Google's MedGemma |
    Demo only - Not for clinical use
    """)


if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
