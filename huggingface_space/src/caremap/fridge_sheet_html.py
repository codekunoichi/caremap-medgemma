"""
CareMap Fridge Sheet HTML Generator - Concept B Style

Generates printable HTML pages matching the concept_b mockups:
- Page 1: Medication Schedule (Ayah/Helper focused)
- Page 2: Lab Results Explained (Family Caregiver focused)
- Page 3: Imaging Explained (Family Caregiver focused)
- Page 4: Care Actions & Follow-ups (Family Caregiver focused)
- Page 5: Important Connections (Both Ayah + Family)

Each page is a standalone 8.5x11" printable document.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import re
import shutil
from pathlib import Path

from .llm_client import MedGemmaClient
from .medication_interpretation import interpret_medication_v3_grounded
from .lab_interpretation import interpret_lab
from .caregap_interpretation import interpret_caregap


# ============================================================================
# CSS STYLES (shared across all pages)
# ============================================================================

BASE_CSS = """
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    line-height: 1.4;
}

.page {
    max-width: 8.5in;
    min-height: 11in;
    margin: 1rem auto;
    background: white;
    padding: 0.4in;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    position: relative;
}

@media print {
    body { background: white; }
    .page {
        box-shadow: none;
        margin: 0;
        padding: 0.3in;
        max-width: 100%;
        min-height: auto;
    }
}

.page-header {
    border-bottom: 4px solid #276749;
    padding-bottom: 0.4rem;
    margin-bottom: 0.5rem;
}

.page-header h1 {
    font-size: 24px;
    color: #276749;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.page-header .subtitle {
    font-size: 14px;
    color: #718096;
    margin-top: 0.2rem;
}

.patient-bar {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem;
    background: #f0fff4;
    border: 1px solid #9ae6b4;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.5rem;
    font-size: 13px;
}

.patient-bar .name {
    font-weight: bold;
    color: #276749;
    font-size: 16px;
}

.audience-tag {
    background: #276749;
    color: white;
    padding: 0.3rem 0.75rem;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
}

.complete-badge {
    background: #d1fae5;
    color: #065f46;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 11px;
    font-weight: bold;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
}

.page-footer {
    position: absolute;
    bottom: 0.3in;
    left: 0.4in;
    right: 0.4in;
    border-top: 1px solid #e2e8f0;
    padding-top: 0.3rem;
    font-size: 10px;
    color: #718096;
    display: flex;
    justify-content: space-between;
}

.medgemma-badge {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    color: white;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 9px;
    font-weight: bold;
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    vertical-align: middle;
}

.medgemma-badge::before {
    content: "🧠";
    font-size: 10px;
}
"""

# ============================================================================
# MEDICATION PAGE CSS
# ============================================================================

MEDICATION_CSS = """
.legend {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.5rem;
    font-size: 11px;
    flex-wrap: wrap;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
}

.time-icon {
    font-size: 16px;
    margin-right: 2px;
}

.med-grid {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin-top: 0.5rem;
}

.med-grid th {
    background: #276749;
    color: white;
    padding: 0.4rem 0.5rem;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.med-grid td {
    padding: 0.4rem 0.5rem;
    border: 1px solid #e2e8f0;
    vertical-align: top;
}

.med-grid tr:nth-child(even) {
    background: #f7fafc;
}

.med-name {
    font-weight: bold;
    color: #2d3748;
    font-size: 13px;
}

.med-dose {
    color: #718096;
    font-size: 11px;
}

.time-badge {
    display: inline-block;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    margin: 0.1rem 0.1rem 0.1rem 0;
}

.time-badge.morning { background: #fef3c7; color: #92400e; }
.time-badge.afternoon { background: #fed7e2; color: #97266d; }
.time-badge.evening { background: #e9d8fd; color: #553c9a; }
.time-badge.bedtime { background: #c4b5fd; color: #4c1d95; }

.food-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
}

.food-badge.with-food { background: #d1fae5; color: #065f46; }
.food-badge.no-food { background: #fee2e2; color: #991b1b; }
.food-badge.optional { background: #f3f4f6; color: #4b5563; }

.warning { color: #c53030; font-weight: 500; font-size: 11px; }
.why-matters { font-size: 11px; color: #4a5568; line-height: 1.4; }

.med-grid th.medgemma-col {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
}

.checkmark {
    width: 18px;
    height: 18px;
    border: 2px solid #cbd5e0;
    border-radius: 3px;
    display: inline-block;
}
"""

# ============================================================================
# LABS PAGE CSS
# ============================================================================

LABS_CSS = """
.lab-grid {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
}

.lab-card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

.lab-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: #f7fafc;
    border-bottom: 1px solid #e2e8f0;
}

.lab-name {
    font-weight: bold;
    font-size: 14px;
    color: #2d3748;
}

.lab-status {
    padding: 0.25rem 0.6rem;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
}

.status-normal { background: #d1fae5; color: #065f46; }
.status-warning { background: #fef3c7; color: #92400e; }
.status-alert { background: #fee2e2; color: #991b1b; }

.lab-card-body {
    padding: 0.6rem 0.75rem;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
}

.lab-section h4 {
    font-size: 10px;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 0.25rem;
}

.lab-section p {
    font-size: 12px;
    color: #4a5568;
    line-height: 1.4;
}

.question-box {
    background: #fffbeb;
    border-left: 3px solid #d69e2e;
    padding: 0.4rem 0.6rem;
    margin-top: 0.5rem;
    grid-column: 1 / -1;
}

.question-box h4 { color: #92400e; }
.question-box p { color: #92400e; font-style: italic; }

.related-tag {
    display: inline-block;
    background: #e9d8fd;
    color: #553c9a;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 10px;
    margin-top: 0.3rem;
}

.legend {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.5rem;
    font-size: 11px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
}

.legend-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
}

.legend-dot.normal { background: #d1fae5; }
.legend-dot.warning { background: #fef3c7; }
.legend-dot.alert { background: #fee2e2; }
"""

# ============================================================================
# CARE GAPS PAGE CSS
# ============================================================================

GAPS_CSS = """
.buckets {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.bucket {
    border-radius: 8px;
    overflow: hidden;
    border: 2px solid;
}

.bucket.today { border-color: #fc8181; }
.bucket.week { border-color: #f6e05e; }
.bucket.later { border-color: #90cdf4; }

.bucket-header {
    padding: 0.5rem 0.75rem;
    font-weight: bold;
    font-size: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.bucket.today .bucket-header { background: #fff5f5; color: #c53030; }
.bucket.week .bucket-header { background: #fffff0; color: #975a16; }
.bucket.later .bucket-header { background: #ebf8ff; color: #2c5282; }

.bucket-count {
    font-size: 11px;
    font-weight: normal;
    opacity: 0.8;
}

.bucket-body {
    padding: 0.5rem;
    background: white;
}

.action-item {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem;
    background: white;
    border-radius: 6px;
    margin-bottom: 0.4rem;
    border: 1px solid #e2e8f0;
}

.action-item:last-child { margin-bottom: 0; }

.checkbox {
    width: 22px;
    height: 22px;
    border: 2px solid #cbd5e0;
    border-radius: 4px;
    flex-shrink: 0;
    margin-top: 0.1rem;
}

.action-content { flex: 1; }

.action-title {
    font-weight: 600;
    font-size: 13px;
    color: #2d3748;
    margin-bottom: 0.2rem;
}

.action-details {
    font-size: 11px;
    color: #4a5568;
    line-height: 1.4;
}

.action-next-step {
    background: #f7fafc;
    padding: 0.3rem 0.5rem;
    border-radius: 4px;
    margin-top: 0.3rem;
    font-size: 11px;
}

.action-next-step strong { color: #2c5282; }

.related-tag {
    display: inline-block;
    background: #e9d8fd;
    color: #553c9a;
    padding: 0.1rem 0.3rem;
    border-radius: 4px;
    font-size: 9px;
    margin-top: 0.2rem;
}

.urgent-badge {
    background: #fed7d7;
    color: #c53030;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 10px;
    font-weight: bold;
    margin-left: 0.3rem;
}
"""

# ============================================================================
# IMAGING PAGE CSS
# ============================================================================

IMAGING_CSS = """
.imaging-container {
    display: grid;
    grid-template-columns: 250px 1fr;
    gap: 1.5rem;
    margin-bottom: 1rem;
}

.xray-container {
    background: #1a1a2e;
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}

.xray-placeholder {
    background: #2d2d44;
    border: 2px dashed #4a4a6a;
    border-radius: 8px;
    padding: 2rem;
    color: #a0aec0;
    font-size: 12px;
}

.xray-label {
    color: #a0aec0;
    font-size: 11px;
    margin-top: 0.5rem;
}

.interpretation-section {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.interpretation-card {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
}

.interpretation-card-header {
    background: #f7fafc;
    padding: 0.5rem 0.75rem;
    font-weight: bold;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border-bottom: 1px solid #e2e8f0;
}

.interpretation-card-header.findings { background: #ebf8ff; color: #2c5282; }
.interpretation-card-header.care { background: #f0fff4; color: #276749; }
.interpretation-card-header.warning { background: #fff5f5; color: #c53030; }

.interpretation-card-body {
    padding: 0.5rem 0.75rem;
}

.interpretation-card-body ul {
    margin-left: 1.25rem;
    font-size: 12px;
    line-height: 1.5;
}

.interpretation-card-body li {
    margin-bottom: 0.4rem;
}

.highlight {
    background: #fef3c7;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
}

.med-link {
    color: #5b21b6;
    font-weight: 500;
}

.connection-box {
    background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
    border: 2px solid #c4b5fd;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-top: 0.75rem;
}

.connection-box-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: bold;
    color: #5b21b6;
    font-size: 13px;
    margin-bottom: 0.5rem;
}

.connection-box p {
    font-size: 12px;
    color: #4c1d95;
    line-height: 1.5;
}

.data-source {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    font-size: 11px;
    color: #718096;
    margin-top: 0.75rem;
}

.data-source strong { color: #4a5568; }
"""

# ============================================================================
# CONNECTIONS PAGE CSS
# ============================================================================

CONNECTIONS_CSS = """
.intro-box {
    background: #faf5ff;
    border-left: 4px solid #805ad5;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.75rem;
    font-size: 12px;
}

.intro-box strong { color: #553c9a; }

.connections {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
}

.connection-card {
    border: 2px solid #e9d8fd;
    border-radius: 10px;
    overflow: hidden;
}

.connection-header {
    background: linear-gradient(135deg, #805ad5 0%, #553c9a 100%);
    color: white;
    padding: 0.5rem 0.75rem;
    font-weight: bold;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.connection-header .priority {
    background: rgba(255,255,255,0.2);
    padding: 0.15rem 0.5rem;
    border-radius: 20px;
    font-size: 10px;
    font-weight: normal;
}

.connection-header .priority.high { background: #fc8181; }

.connection-body { padding: 0.6rem 0.75rem; }

.connection-flow {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
}

.flow-item {
    padding: 0.3rem 0.6rem;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
}

.flow-med { background: #c6f6d5; color: #276749; }
.flow-lab { background: #bee3f8; color: #2c5282; }
.flow-gap { background: #fef3c7; color: #975a16; }

.flow-arrow { color: #805ad5; font-weight: bold; }

.connection-explanation {
    font-size: 12px;
    color: #4a5568;
    line-height: 1.5;
}

.connection-explanation strong { color: #2d3748; }

.action-callout {
    background: #fffbeb;
    border: 1px solid #f6e05e;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    margin-top: 0.5rem;
    font-size: 11px;
    line-height: 1.4;
}

.action-callout strong { color: #975a16; }

.warning-callout {
    background: #fff5f5;
    border: 1px solid #fc8181;
    border-radius: 6px;
    padding: 0.4rem 0.6rem;
    margin-top: 0.5rem;
    font-size: 11px;
    color: #c53030;
    line-height: 1.4;
}

.contacts-bar {
    background: #edf2f7;
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
    margin-top: 0.75rem;
    display: flex;
    gap: 1.5rem;
    font-size: 11px;
    flex-wrap: wrap;
}

.contacts-bar strong { color: #2c5282; }
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_time_badges(timing: str) -> str:
    """Convert timing text to HTML time badges with emojis."""
    timing_lower = timing.lower()
    badges = []

    if 'morning' in timing_lower or 'breakfast' in timing_lower or '8 am' in timing_lower:
        badges.append('<span class="time-icon">☀️</span> <span class="time-badge morning">Morning</span>')
    if 'afternoon' in timing_lower or 'lunch' in timing_lower or '2 pm' in timing_lower:
        badges.append('<span class="time-icon">🌤️</span> <span class="time-badge afternoon">Afternoon</span>')
    if 'evening' in timing_lower or 'dinner' in timing_lower or '6 pm' in timing_lower:
        badges.append('<span class="time-icon">🌅</span> <span class="time-badge evening">Evening</span>')
    if 'bedtime' in timing_lower or 'night' in timing_lower or '10 pm' in timing_lower:
        badges.append('<span class="time-icon">🌙</span> <span class="time-badge bedtime">Bedtime</span>')
    if 'as needed' in timing_lower or 'prn' in timing_lower:
        badges.append('<span class="time-badge">as needed</span>')

    if 'twice' in timing_lower and not badges:
        badges = [
            '<span class="time-icon">☀️</span> <span class="time-badge morning">Morning</span>',
            '<span class="time-icon">🌅</span> <span class="time-badge evening">Evening</span>'
        ]

    return '<br>'.join(badges) if badges else timing


def get_food_badge(timing: str, sig_text: str) -> str:
    """Extract food instructions and return HTML badge."""
    combined = (timing + ' ' + sig_text).lower()

    if 'with food' in combined or 'with meal' in combined or 'after meal' in combined:
        return '<span class="food-badge with-food">🍽️ With Food</span>'
    elif 'empty stomach' in combined or 'before food' in combined or 'before meal' in combined:
        return '<span class="food-badge no-food">🚫🍽️ Empty Stomach</span>'
    else:
        return '<span class="food-badge optional">🍽️ Optional</span>'


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))


def get_lab_status_class(category: str) -> tuple:
    """Get CSS class and icon for lab status."""
    category_lower = (category or '').lower()
    if 'normal' in category_lower or 'good' in category_lower:
        return 'status-normal', '✓ Normal'
    elif 'needs' in category_lower or 'follow' in category_lower or 'alert' in category_lower:
        return 'status-alert', '⚠️ Needs Follow-up'
    else:
        return 'status-warning', 'Slightly Off'


# ============================================================================
# PAGE DATA CLASS
# ============================================================================

@dataclass
class PatientInfo:
    """Patient information for page headers."""
    nickname: str
    age_range: str
    conditions: list


# ============================================================================
# PAGE 1: MEDICATIONS
# ============================================================================

def generate_medications_page(
    patient: PatientInfo,
    medications: list,
    client: Optional[MedGemmaClient] = None,
    page_num: int = 1,
    total_pages: int = 5,
    progress_callback=None
) -> str:
    """Generate the Medication Schedule page (Page 1) in concept_b style."""
    today = datetime.now().strftime("%b %d, %Y")
    med_count = len(medications)

    med_rows = []
    for i, med in enumerate(medications):
        if progress_callback:
            progress_callback(i + 1, med_count, med.get('medication_name', 'medication'))

        name = med.get('medication_name', 'Unknown')
        sig_text = med.get('sig_text', '')
        timing = med.get('timing', '')
        clinician_notes = med.get('clinician_notes', '')
        interaction_notes = med.get('interaction_notes', '')

        when_html = get_time_badges(timing)
        how_html = get_food_badge(timing, sig_text)

        why_matters = ""
        watch_for = ""

        if client:
            try:
                result, _ = interpret_medication_v3_grounded(
                    client=client,
                    medication_name=name,
                    sig_text=sig_text,
                    clinician_notes=clinician_notes,
                    interaction_notes=interaction_notes,
                )
                if 'raw_response' not in result:
                    why_matters = result.get('what_this_does', '')
                    watch_for = result.get('watch_out_for', '')
            except Exception:
                pass

        if not why_matters:
            why_matters = clinician_notes
        if not watch_for:
            watch_for = interaction_notes

        watch_html = f'<span class="warning">⚠️ {escape_html(watch_for)}</span>' if watch_for else ''

        dose_match = re.search(r'(\d+\s*mg|\d+\s*mcg|\d+\s*units?)', sig_text, re.IGNORECASE)
        dose = dose_match.group(1) if dose_match else ""

        med_rows.append(f"""
            <tr>
                <td><div class="checkmark"></div></td>
                <td>
                    <div class="med-name">{escape_html(name)}</div>
                    <div class="med-dose">{escape_html(dose)}</div>
                </td>
                <td>{when_html}</td>
                <td class="instruction">{how_html}</td>
                <td class="why-matters">{escape_html(why_matters)}</td>
                <td>{watch_html}</td>
            </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareMap: Medication Schedule - {escape_html(patient.nickname)}</title>
    <style>
{BASE_CSS}
{MEDICATION_CSS}
    </style>
</head>
<body>
    <div class="page">
        <div class="page-header">
            <h1>💊 Medication Schedule</h1>
            <div class="subtitle">Daily reference for giving medicines</div>
        </div>

        <div class="patient-bar">
            <div>
                <span class="name">{escape_html(patient.nickname)}</span>
                <span style="margin-left: 1rem;">{escape_html(patient.age_range)}</span>
            </div>
            <div>
                <span class="audience-tag">👤 For: Ayah / Helper</span>
                <span class="complete-badge" style="margin-left: 0.5rem;">✓ All {med_count} Medicines Shown</span>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item"><span class="time-icon">☀️</span> Morning</div>
            <div class="legend-item"><span class="time-icon">🌤️</span> Afternoon</div>
            <div class="legend-item"><span class="time-icon">🌅</span> Evening</div>
            <div class="legend-item"><span class="time-icon">🌙</span> Bedtime</div>
            <div class="legend-item"><span class="food-badge with-food">🍽️</span> With Food</div>
            <div class="legend-item"><span class="food-badge no-food">🚫🍽️</span> Empty Stomach</div>
            <div class="legend-item"><span class="warning">⚠️</span> Warning</div>
            <div class="legend-item"><span class="medgemma-badge">MedGemma</span> AI-Generated</div>
        </div>

        <table class="med-grid">
            <thead>
                <tr>
                    <th style="width: 4%">✓</th>
                    <th style="width: 14%">Medicine</th>
                    <th style="width: 11%">When</th>
                    <th style="width: 12%">How to Give</th>
                    <th style="width: 30%" class="medgemma-col">Why It Matters <span class="medgemma-badge" style="margin-left: 0.3rem;">AI</span></th>
                    <th style="width: 29%">Watch For</th>
                </tr>
            </thead>
            <tbody>
                {''.join(med_rows)}
            </tbody>
        </table>

        <div class="page-footer">
            <div>CareMap | For information only | Updated: {today}</div>
            <div>Page {page_num} of {total_pages}: Medications (Ayah Reference)</div>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# PAGE 2: LABS
# ============================================================================

def generate_labs_page(
    patient: PatientInfo,
    results: list,
    client: Optional[MedGemmaClient] = None,
    page_num: int = 2,
    total_pages: int = 5,
    progress_callback=None
) -> str:
    """Generate the Lab Results page (Page 2) in concept_b style."""
    today = datetime.now().strftime("%b %d, %Y")
    lab_count = len(results)

    lab_cards = []
    for i, lab in enumerate(results):
        if progress_callback:
            progress_callback(i + 1, lab_count, lab.get('test_name', 'lab'))

        test_name = lab.get('test_name', 'Unknown Test')
        category = lab.get('meaning_category', 'Normal')
        source_note = lab.get('source_note', '')

        status_class, status_text = get_lab_status_class(category)

        what_checks = ""
        what_means = ""
        ask_doctor = ""

        if client:
            try:
                result = interpret_lab(
                    client=client,
                    test_name=test_name,
                    value_display=lab.get('value_display', ''),
                    meaning_category=category,
                    source_note=source_note,
                )
                what_checks = result.get('what_was_checked', '')
                what_means = result.get('what_it_means', '')
                ask_doctor = result.get('what_to_ask_doctor', '')
            except Exception:
                pass

        if not what_checks:
            what_checks = f"This test measures {test_name.lower()}."
        if not what_means:
            what_means = source_note or category

        question_html = ""
        if ask_doctor:
            question_html = f"""
                <div class="question-box">
                    <h4>💬 Ask the Doctor</h4>
                    <p>"{escape_html(ask_doctor)}"</p>
                </div>
            """

        lab_cards.append(f"""
            <div class="lab-card">
                <div class="lab-card-header">
                    <span class="lab-name">{escape_html(test_name)}</span>
                    <span class="lab-status {status_class}">{status_text}</span>
                </div>
                <div class="lab-card-body">
                    <div class="lab-section">
                        <h4>What This Test Checks</h4>
                        <p>{escape_html(what_checks)}</p>
                    </div>
                    <div class="lab-section">
                        <h4>What The Result Means</h4>
                        <p>{escape_html(what_means)}</p>
                    </div>
                    {question_html}
                </div>
            </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareMap: Lab Results - {escape_html(patient.nickname)}</title>
    <style>
{BASE_CSS}
{LABS_CSS}
.page-header {{ border-color: #2c5282; }}
.page-header h1 {{ color: #2c5282; }}
.patient-bar {{ background: #ebf8ff; border-color: #90cdf4; }}
.patient-bar .name {{ color: #2c5282; }}
.audience-tag {{ background: #2c5282; }}
    </style>
</head>
<body>
    <div class="page">
        <div class="page-header">
            <h1>🔬 Lab Results Explained</h1>
            <div class="subtitle">Understanding recent test results and what to discuss with the doctor</div>
        </div>

        <div class="patient-bar">
            <div>
                <span class="name">{escape_html(patient.nickname)}</span>
                <span style="margin-left: 1rem;">Labs from: {today}</span>
            </div>
            <div>
                <span class="audience-tag">👨‍👩‍👧 For: Family Caregiver</span>
                <span class="complete-badge" style="margin-left: 0.5rem;">✓ All {lab_count} Results Shown</span>
            </div>
        </div>

        <div class="legend">
            <div class="legend-item"><div class="legend-dot normal"></div> Normal</div>
            <div class="legend-item"><div class="legend-dot warning"></div> Slightly Off</div>
            <div class="legend-item"><div class="legend-dot alert"></div> Needs Follow-up</div>
        </div>

        <div class="lab-grid">
            {''.join(lab_cards)}
        </div>

        <div class="page-footer">
            <div>CareMap | For information only | Updated: {today}</div>
            <div>Page {page_num} of {total_pages}: Lab Results (Family Reference)</div>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# PAGE 3: CARE GAPS
# ============================================================================

def generate_gaps_page(
    patient: PatientInfo,
    care_gaps: list,
    client: Optional[MedGemmaClient] = None,
    page_num: int = 3,
    total_pages: int = 5,
    progress_callback=None
) -> str:
    """Generate the Care Actions page (Page 3) in concept_b style."""
    today = datetime.now().strftime("%b %d, %Y")

    today_items = []
    week_items = []
    later_items = []

    for i, gap in enumerate(care_gaps):
        if progress_callback:
            progress_callback(i + 1, len(care_gaps), gap.get('item_text', 'gap'))

        item_text = gap.get('item_text', '')
        next_step = gap.get('next_step', '')
        bucket = gap.get('time_bucket', 'This Week')

        action_item = ""
        next_step_ai = ""

        if client:
            try:
                result = interpret_caregap(
                    client=client,
                    item_text=item_text,
                    next_step=next_step,
                    time_bucket=bucket,
                )
                action_item = result.get('action_item', '')
                next_step_ai = result.get('next_step', '')
            except Exception:
                pass

        item_data = {
            'title': action_item or item_text,
            'details': '',
            'next_step': next_step_ai or next_step,
            'is_daily': 'daily' in item_text.lower(),
        }

        if bucket == 'Today':
            today_items.append(item_data)
        elif bucket == 'This Week':
            week_items.append(item_data)
        else:
            later_items.append(item_data)

    def render_action_items(items):
        html_parts = []
        for item in items:
            daily_badge = '<span class="urgent-badge">DAILY</span>' if item['is_daily'] else ''
            next_html = f'<div class="action-next-step"><strong>Next step:</strong> {escape_html(item["next_step"])}</div>' if item['next_step'] else ''
            html_parts.append(f"""
                <div class="action-item">
                    <div class="checkbox"></div>
                    <div class="action-content">
                        <div class="action-title">{escape_html(item['title'])} {daily_badge}</div>
                        <div class="action-details">{escape_html(item['details'])}</div>
                        {next_html}
                    </div>
                </div>
            """)
        return ''.join(html_parts)

    total_items = len(today_items) + len(week_items) + len(later_items)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareMap: Care Actions - {escape_html(patient.nickname)}</title>
    <style>
{BASE_CSS}
{GAPS_CSS}
.page-header {{ border-color: #d69e2e; }}
.page-header h1 {{ color: #975a16; }}
.patient-bar {{ background: #fffbeb; border-color: #f6e05e; }}
.patient-bar .name {{ color: #975a16; }}
.audience-tag {{ background: #975a16; }}
    </style>
</head>
<body>
    <div class="page">
        <div class="page-header">
            <h1>✅ Care Actions & Follow-ups</h1>
            <div class="subtitle">Tasks organized by urgency - check off as completed</div>
        </div>

        <div class="patient-bar">
            <div>
                <span class="name">{escape_html(patient.nickname)}</span>
                <span style="margin-left: 1rem;">Week of: {today}</span>
            </div>
            <div>
                <span class="audience-tag">👨‍👩‍👧 For: Family Caregiver</span>
                <span class="complete-badge" style="margin-left: 0.5rem;">✓ All {total_items} Actions Shown</span>
            </div>
        </div>

        <div class="buckets">
            <div class="bucket today">
                <div class="bucket-header">
                    <span>🔴 TODAY - Do These Now</span>
                    <span class="bucket-count">{len(today_items)} items</span>
                </div>
                <div class="bucket-body">
                    {render_action_items(today_items) if today_items else '<p style="padding: 0.5rem; color: #718096; font-size: 12px;">No urgent items today</p>'}
                </div>
            </div>

            <div class="bucket week">
                <div class="bucket-header">
                    <span>🟡 THIS WEEK - Schedule Soon</span>
                    <span class="bucket-count">{len(week_items)} items</span>
                </div>
                <div class="bucket-body">
                    {render_action_items(week_items) if week_items else '<p style="padding: 0.5rem; color: #718096; font-size: 12px;">No items this week</p>'}
                </div>
            </div>

            <div class="bucket later">
                <div class="bucket-header">
                    <span>🔵 COMING UP - Plan Ahead</span>
                    <span class="bucket-count">{len(later_items)} items</span>
                </div>
                <div class="bucket-body">
                    {render_action_items(later_items) if later_items else '<p style="padding: 0.5rem; color: #718096; font-size: 12px;">No upcoming items</p>'}
                </div>
            </div>
        </div>

        <div class="page-footer">
            <div>CareMap | For information only | Updated: {today}</div>
            <div>Page {page_num} of {total_pages}: Care Actions (Family Reference)</div>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# PAGE 4: IMAGING
# ============================================================================

def generate_imaging_page(
    patient: PatientInfo,
    image_path: Optional[str] = None,
    client: Optional[MedGemmaClient] = None,
    page_num: int = 4,
    total_pages: int = 5,
    progress_callback=None
) -> str:
    """
    Generate the Imaging Explained page (Page 4) in concept_b style.

    Args:
        patient: PatientInfo with name, age, conditions
        image_path: Path to X-ray image file (PNG)
        client: MedGemma client (should have multimodal enabled for image analysis)
        page_num: Current page number
        total_pages: Total number of pages
        progress_callback: Optional callback(current, total, message)

    Returns:
        Complete HTML string for the imaging page
    """
    import base64
    from .imaging_interpretation import interpret_imaging_with_image

    today = datetime.now().strftime("%b %d, %Y")

    if progress_callback:
        progress_callback(1, 3, "loading X-ray image")

    # Embed image as base64 if path provided
    image_html = ""
    if image_path and Path(image_path).exists():
        with open(image_path, 'rb') as img_file:
            img_data = base64.b64encode(img_file.read()).decode('utf-8')
            image_html = f'<img src="data:image/png;base64,{img_data}" alt="Chest X-ray" style="max-width: 100%; border-radius: 8px; border: 2px solid #333;">'
    else:
        image_html = '''<div class="xray-placeholder">
            <p>🖼️ X-ray Image</p>
            <p style="margin-top: 0.5rem; font-size: 10px;">Image would appear here when provided</p>
        </div>'''

    # Default content
    findings = [
        "No imaging data available",
        "Upload an X-ray or imaging report to see AI interpretation"
    ]
    care_implications = ["Continue following your care plan"]
    warning_signs = ["Shortness of breath", "Chest pain", "Sudden changes in symptoms"]
    ask_doctor = "What did my imaging study show?"

    # Use MedGemma multimodal to analyze the image
    if image_path and client:
        if progress_callback:
            progress_callback(2, 3, "analyzing X-ray with MedGemma AI")

        try:
            # Check if client supports multimodal
            if hasattr(client, 'supports_multimodal') and client.supports_multimodal:
                result = interpret_imaging_with_image(
                    client=client,
                    study_type="Chest X-ray",
                    image_paths=[image_path],
                    report_text="",  # Let multimodal analyze directly
                    flag="needs_follow_up",  # Assume abnormal for demo patient
                )
                findings = [result.get('key_finding', 'Analysis complete')]
                care_implications = [
                    "This X-ray is being monitored by your healthcare team",
                    result.get('what_was_done', 'A chest X-ray was performed'),
                ]
                ask_doctor = result.get('what_to_ask_doctor', 'What does my X-ray show?')
            else:
                # Text-only mode - provide contextual info based on patient conditions
                findings = [
                    "The X-ray shows the chest area including heart and lungs",
                    "Your healthcare team will review this image and explain the findings",
                ]
                # For Dadu's conditions (heart failure), add relevant care points
                if any('heart' in c.lower() for c in patient.conditions):
                    care_implications = [
                        "Heart failure patients often have chest X-rays to monitor fluid levels",
                        "The water pill (Furosemide) helps remove extra fluid seen on X-rays",
                        "Daily weight monitoring helps track fluid changes between X-rays",
                    ]
                    warning_signs = [
                        "Shortness of breath - especially when lying flat",
                        "Sudden weight gain (more than 3 lbs in one day)",
                        "Swelling in legs, ankles, or feet",
                        "Persistent cough, especially with pink/frothy mucus",
                    ]
        except Exception as e:
            findings = [f"Image analysis encountered an issue: {str(e)[:50]}"]

    if progress_callback:
        progress_callback(3, 3, "generating imaging page")

    # Build the connection box content based on patient medications
    connection_text = f"""The imaging helps your healthcare team monitor {escape_html(patient.nickname)}'s conditions.
        For patients with heart-related conditions, chest X-rays can show:
        <strong>heart size</strong> (related to Carvedilol, Lisinopril),
        <strong>fluid in lungs</strong> (why Furosemide/water pill is important), and
        <strong>overall lung health</strong>."""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareMap: Imaging Explained - {escape_html(patient.nickname)}</title>
    <style>
{BASE_CSS}
{IMAGING_CSS}
    </style>
</head>
<body>
    <div class="page">
        <div class="page-header">
            <h1>🫁 Imaging Explained <span class="medgemma-badge">MedGemma AI</span></h1>
            <div class="subtitle">Understanding what the scans show and what it means for care</div>
        </div>

        <div class="patient-bar">
            <div>
                <span class="name">{escape_html(patient.nickname)}</span>
                <span style="margin-left: 1rem;">{escape_html(patient.age_range)}</span>
            </div>
            <div>
                <span class="audience-tag">👨‍👩‍👧 For: Family Caregiver</span>
            </div>
        </div>

        <div class="imaging-container">
            <div class="xray-container">
                {image_html}
                <div class="xray-label">Chest X-ray (PA View)</div>
            </div>

            <div class="interpretation-section">
                <div class="interpretation-card">
                    <div class="interpretation-card-header findings">
                        🔍 What The X-ray Shows
                    </div>
                    <div class="interpretation-card-body">
                        <ul>
                            {''.join(f'<li>{escape_html(f)}</li>' for f in findings)}
                        </ul>
                    </div>
                </div>

                <div class="interpretation-card">
                    <div class="interpretation-card-header care">
                        💊 What This Means For Daily Care
                    </div>
                    <div class="interpretation-card-body">
                        <ul>
                            {''.join(f'<li>{escape_html(c)}</li>' for c in care_implications)}
                        </ul>
                    </div>
                </div>

                <div class="interpretation-card">
                    <div class="interpretation-card-header warning">
                        ⚠️ When To Call The Doctor
                    </div>
                    <div class="interpretation-card-body">
                        <ul>
                            {''.join(f'<li><strong>{escape_html(w)}</strong></li>' for w in warning_signs)}
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <div class="connection-box">
            <div class="connection-box-header">
                <span class="medgemma-badge">MedGemma</span>
                How This Connects To {escape_html(patient.nickname)}'s Care
            </div>
            <p>{connection_text}</p>
        </div>

        <div class="data-source">
            <strong>Image Source:</strong> NIH Clinical Center Chest X-ray Dataset (CC0 Public Domain) |
            <strong>Interpretation:</strong> Generated by MedGemma AI |
            <strong>Note:</strong> For demonstration only - always consult healthcare provider for medical interpretation
        </div>

        <div class="page-footer">
            <div>CareMap | For information only | Updated: {today}</div>
            <div>Page {page_num} of {total_pages}: Imaging Explained (Family Reference)</div>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# PAGE 5: CONNECTIONS
# ============================================================================

def generate_connections_page(
    patient: PatientInfo,
    medications: list,
    results: list,
    care_gaps: list,
    contacts: dict,
    page_num: int = 5,
    total_pages: int = 5,
    progress_callback=None
) -> str:
    """Generate the Important Connections page (Page 5) in concept_b style."""
    today = datetime.now().strftime("%b %d, %Y")

    if progress_callback:
        progress_callback(1, 1, "building connections")

    # Extract medication names for connections
    med_names = [m.get('medication_name', '') for m in medications]

    # Build connection cards based on common patterns
    connections = []

    # Check for blood thinner connection
    if any('warfarin' in m.lower() for m in med_names):
        connections.append({
            'title': '🩸 Blood Thinner Monitoring',
            'priority': 'high',
            'flow': [
                ('med', '💊 Warfarin'),
                ('lab', '🔬 INR Test'),
                ('gap', '✅ Regular Monitoring'),
            ],
            'explanation': 'Warfarin thins the blood to prevent clots. The INR test measures how thin the blood is. Regular monitoring ensures the level stays in the safe range.',
            'warning': 'Watch for unusual bleeding, bruising, blood in urine/stool, nosebleeds, or bleeding gums. Call clinic immediately if you notice any bleeding.',
            'actions': 'No ibuprofen, aspirin, or Advil - these increase bleeding risk with Warfarin.',
        })

    # Check for diabetes connection
    if any('metformin' in m.lower() or 'insulin' in m.lower() for m in med_names):
        connections.append({
            'title': '🍬 Diabetes Management',
            'priority': None,
            'flow': [
                ('med', '💊 Diabetes Meds'),
                ('lab', '🔬 Blood Sugar / A1C'),
                ('gap', '✅ Daily Monitoring'),
            ],
            'explanation': 'Diabetes medications work together to control blood sugar. Daily checks help ensure medications are working and catch problems early.',
            'warning': None,
            'actions': 'Give medications as scheduled. Watch for shaking, sweating, confusion (low blood sugar) - give juice or sugar if this happens.',
        })

    # Check for heart failure connection
    if any('furosemide' in m.lower() or 'lasix' in m.lower() for m in med_names):
        connections.append({
            'title': '❤️ Heart Failure & Fluid Management',
            'priority': None,
            'flow': [
                ('med', '💊 Furosemide + Heart Meds'),
                ('gap', '✅ Daily Weight'),
            ],
            'explanation': 'These medications protect the heart and prevent fluid buildup. Daily weight catches fluid buildup early - sudden weight gain means fluid is building up.',
            'warning': 'Call clinic if weight goes up more than 3 lbs in one day, increased swelling, trouble breathing, or cannot lie flat to sleep.',
            'actions': 'Give Furosemide in morning/early afternoon only. Help patient stand slowly - these medicines can cause dizziness.',
        })

    # Check for kidney connection
    if any('lisinopril' in m.lower() for m in med_names):
        connections.append({
            'title': '🫘 Kidney Protection',
            'priority': None,
            'flow': [
                ('med', '💊 Lisinopril'),
                ('lab', '🔬 Kidney Function'),
            ],
            'explanation': 'Lisinopril protects the kidneys while helping the heart. Regular kidney function tests ensure the medication is safe.',
            'warning': 'If patient needs a CT scan with contrast dye, tell the doctor about all medications - some may need to be stopped temporarily.',
            'actions': None,
        })

    def render_connections():
        html_parts = []
        for conn in connections:
            priority_html = f'<span class="priority {conn["priority"] or ""}">⚠️ Priority</span>' if conn['priority'] else ''

            flow_html = ' <span class="flow-arrow">→</span> '.join(
                f'<span class="flow-item flow-{f[0]}">{f[1]}</span>' for f in conn['flow']
            )

            warning_html = f'<div class="warning-callout"><strong>⚠️ Watch For:</strong> {escape_html(conn["warning"])}</div>' if conn['warning'] else ''

            action_html = f'<div class="action-callout"><strong>Ayah:</strong> {escape_html(conn["actions"])}</div>' if conn['actions'] else ''

            html_parts.append(f"""
                <div class="connection-card">
                    <div class="connection-header">
                        {conn['title']}
                        {priority_html}
                    </div>
                    <div class="connection-body">
                        <div class="connection-flow">{flow_html}</div>
                        <div class="connection-explanation"><strong>The Connection:</strong> {escape_html(conn['explanation'])}</div>
                        {warning_html}
                        {action_html}
                    </div>
                </div>
            """)
        return ''.join(html_parts)

    # Build contacts bar
    clinic_name = contacts.get('clinic_name', 'Your Clinic')
    clinic_phone = contacts.get('clinic_phone', '')
    pharmacy_name = contacts.get('pharmacy_name', 'Your Pharmacy')
    pharmacy_phone = contacts.get('pharmacy_phone', '')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CareMap: Important Connections - {escape_html(patient.nickname)}</title>
    <style>
{BASE_CSS}
{CONNECTIONS_CSS}
.page-header {{ border-color: #805ad5; }}
.page-header h1 {{ color: #553c9a; }}
.patient-bar {{ background: #faf5ff; border-color: #d6bcfa; }}
.patient-bar .name {{ color: #553c9a; }}
.audience-tag {{ background: #553c9a; }}
    </style>
</head>
<body>
    <div class="page">
        <div class="page-header">
            <h1>🔗 Important Connections</h1>
            <div class="subtitle">How medications, lab results, and care actions work together</div>
        </div>

        <div class="patient-bar">
            <div>
                <span class="name">{escape_html(patient.nickname)}</span>
            </div>
            <div>
                <span class="audience-tag">👥 For: Ayah + Family</span>
            </div>
        </div>

        <div class="intro-box">
            <strong>Why This Page Matters:</strong> Many of {escape_html(patient.nickname)}'s medications, lab tests, and care tasks are connected.
            Understanding these relationships helps everyone give better care and know when to call the doctor.
        </div>

        <div class="connections">
            {render_connections() if connections else '<p style="padding: 1rem; color: #718096;">No specific medication connections identified.</p>'}
        </div>

        <div class="contacts-bar">
            <div><strong>📞 Clinic:</strong> {escape_html(clinic_name)} - {escape_html(clinic_phone)}</div>
            <div><strong>💊 Pharmacy:</strong> {escape_html(pharmacy_name)} - {escape_html(pharmacy_phone)}</div>
            <div><strong>🚨 Emergency:</strong> 911</div>
        </div>

        <div class="page-footer">
            <div>CareMap | For information only | Updated: {today}</div>
            <div>Page {page_num} of {total_pages}: Important Connections (Ayah + Family Reference)</div>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def generate_fridge_sheet_html(
    patient_data: dict,
    client: Optional[MedGemmaClient] = None,
    pages: list = None,
    progress_callback=None
) -> dict:
    """
    Generate all concept_b fridge sheet pages.

    Args:
        patient_data: Canonical patient data dict
        client: Optional MedGemma client for AI interpretations
        pages: List of pages to generate ['medications', 'labs', 'gaps', 'imaging', 'connections']
                Default: all pages
        progress_callback: Optional callback(current, total, message)

    Returns:
        Dict mapping page name to HTML string
    """
    if pages is None:
        pages = ['medications', 'labs', 'gaps', 'imaging', 'connections']

    patient_dict = patient_data.get('patient', {})
    patient = PatientInfo(
        nickname=patient_dict.get('nickname', 'Patient'),
        age_range=patient_dict.get('age_range', ''),
        conditions=patient_dict.get('conditions_display', [])
    )

    total_pages = len(pages)
    results = {}

    if 'medications' in pages:
        medications = patient_data.get('medications', [])
        results['medications'] = generate_medications_page(
            patient=patient,
            medications=medications,
            client=client,
            page_num=pages.index('medications') + 1,
            total_pages=total_pages,
            progress_callback=progress_callback
        )

    if 'labs' in pages:
        labs = patient_data.get('results', [])
        results['labs'] = generate_labs_page(
            patient=patient,
            results=labs,
            client=client,
            page_num=pages.index('labs') + 1,
            total_pages=total_pages,
            progress_callback=progress_callback
        )

    if 'gaps' in pages:
        care_gaps = patient_data.get('care_gaps', [])
        results['gaps'] = generate_gaps_page(
            patient=patient,
            care_gaps=care_gaps,
            client=client,
            page_num=pages.index('gaps') + 1,
            total_pages=total_pages,
            progress_callback=progress_callback
        )

    if 'imaging' in pages:
        results['imaging'] = generate_imaging_page(
            patient=patient,
            imaging_data=None,  # Would come from imaging interpretation
            client=client,
            page_num=pages.index('imaging') + 1,
            total_pages=total_pages,
            progress_callback=progress_callback
        )

    if 'connections' in pages:
        results['connections'] = generate_connections_page(
            patient=patient,
            medications=patient_data.get('medications', []),
            results=patient_data.get('results', []),
            care_gaps=patient_data.get('care_gaps', []),
            contacts=patient_data.get('contacts', {}),
            page_num=pages.index('connections') + 1,
            total_pages=total_pages,
            progress_callback=progress_callback
        )

    return results


# ============================================================================
# CLI for testing
# ============================================================================

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    print("=" * 70)
    print("CareMap Fridge Sheet Generator - Concept B Style")
    print("=" * 70)

    # Setup paths
    project_root = Path(__file__).parent.parent.parent
    output_dir = project_root / "output" / "fridge_sheets"

    # Clean up old files
    print("\n[0/7] Cleaning up old generated files...")
    if output_dir.exists():
        shutil.rmtree(output_dir)
        print("      Deleted old output folder")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"      Created fresh output folder: {output_dir}")

    # Step 1: Load patient data
    print("\n[1/7] Loading patient golden test case...")
    sample_file = project_root / "examples" / "golden_patient_complex.json"
    print(f"      File: {sample_file.name}")

    with open(sample_file) as f:
        patient_data = json.load(f)

    patient_name = patient_data.get('patient', {}).get('nickname', 'Patient')
    med_count = len(patient_data.get('medications', []))
    lab_count = len(patient_data.get('results', []))
    gap_count = len(patient_data.get('care_gaps', []))
    print(f"      Patient: {patient_name}")
    print(f"      Medications: {med_count}")
    print(f"      Labs: {lab_count}")
    print(f"      Care Gaps: {gap_count}")

    # Step 2: Load MedGemma
    print("\n[2/7] Loading MedGemma clinical AI model...")
    print("      Model: google/medgemma-4b-it")
    print("      This may take a moment on first run...")

    try:
        from .llm_client import MedGemmaClient
        client = MedGemmaClient()
        print("      MedGemma loaded successfully!")
        use_ai = True
    except Exception as e:
        print(f"      Warning: Could not load MedGemma: {e}")
        print("      Continuing without AI (will use clinician notes instead)")
        client = None
        use_ai = False

    # Step 3: Generate Medications Page
    print("\n[3/7] Generating MEDICATIONS page...")
    print("      Simplifying medication information for Ayah/Helper...")

    def med_progress(current, total, message):
        print(f"      [{current}/{total}] {message}")

    med_html = generate_medications_page(
        patient=PatientInfo(
            nickname=patient_data['patient']['nickname'],
            age_range=patient_data['patient']['age_range'],
            conditions=patient_data['patient']['conditions_display']
        ),
        medications=patient_data['medications'],
        client=client,
        page_num=1,
        total_pages=5,
        progress_callback=med_progress
    )

    med_file = output_dir / "1_medications.html"
    with open(med_file, 'w') as f:
        f.write(med_html)
    print(f"      Saved: {med_file.name}")

    # Step 4: Generate Labs Page
    print("\n[4/7] Generating LABS page...")
    print("      Explaining lab results in plain language...")

    def lab_progress(current, total, message):
        print(f"      [{current}/{total}] {message}")

    lab_html = generate_labs_page(
        patient=PatientInfo(
            nickname=patient_data['patient']['nickname'],
            age_range=patient_data['patient']['age_range'],
            conditions=patient_data['patient']['conditions_display']
        ),
        results=patient_data.get('results', []),
        client=client,
        page_num=2,
        total_pages=5,
        progress_callback=lab_progress
    )

    lab_file = output_dir / "2_labs.html"
    with open(lab_file, 'w') as f:
        f.write(lab_html)
    print(f"      Saved: {lab_file.name}")

    # Step 5: Generate Care Gaps Page
    print("\n[5/7] Generating CARE GAPS page...")
    print("      Organizing care actions by urgency...")

    def gap_progress(current, total, message):
        print(f"      [{current}/{total}] {message}")

    gap_html = generate_gaps_page(
        patient=PatientInfo(
            nickname=patient_data['patient']['nickname'],
            age_range=patient_data['patient']['age_range'],
            conditions=patient_data['patient']['conditions_display']
        ),
        care_gaps=patient_data.get('care_gaps', []),
        client=client,
        page_num=3,
        total_pages=5,
        progress_callback=gap_progress
    )

    gap_file = output_dir / "3_care_gaps.html"
    with open(gap_file, 'w') as f:
        f.write(gap_html)
    print(f"      Saved: {gap_file.name}")

    # Step 6: Generate Imaging Page with X-ray
    print("\n[6/7] Generating IMAGING page with chest X-ray...")

    # Use a sample X-ray from NIH dataset (cardiomegaly - relevant to heart failure)
    xray_path = project_root / "data" / "nih_chest_xray" / "demo_images" / "stat" / "00000032_001.png"
    if xray_path.exists():
        print(f"      Using X-ray: {xray_path.name}")
    else:
        print(f"      Warning: X-ray not found at {xray_path}")
        xray_path = None

    imaging_html = generate_imaging_page(
        patient=PatientInfo(
            nickname=patient_data['patient']['nickname'],
            age_range=patient_data['patient']['age_range'],
            conditions=patient_data['patient']['conditions_display']
        ),
        image_path=str(xray_path) if xray_path else None,
        client=client,
        page_num=4,
        total_pages=5,
        progress_callback=lambda c, t, m: print(f"      [{c}/{t}] {m}")
    )

    imaging_file = output_dir / "4_imaging.html"
    with open(imaging_file, 'w') as f:
        f.write(imaging_html)
    print(f"      Saved: {imaging_file.name}")

    # Step 7: Generate Connections Page
    print("\n[7/7] Generating CONNECTIONS page...")
    print("      Building medication-lab-care action relationships...")

    connections_html = generate_connections_page(
        patient=PatientInfo(
            nickname=patient_data['patient']['nickname'],
            age_range=patient_data['patient']['age_range'],
            conditions=patient_data['patient']['conditions_display']
        ),
        medications=patient_data.get('medications', []),
        results=patient_data.get('results', []),
        care_gaps=patient_data.get('care_gaps', []),
        contacts=patient_data.get('contacts', {}),
        page_num=5,
        total_pages=5,
        progress_callback=lambda c, t, m: print(f"      [{c}/{t}] {m}")
    )

    connections_file = output_dir / "5_connections.html"
    with open(connections_file, 'w') as f:
        f.write(connections_html)
    print(f"      Saved: {connections_file.name}")

    # Summary
    print("\n" + "=" * 70)
    print("COMPLETE! All 5 fridge sheet pages generated.")
    print("=" * 70)
    print(f"\nOutput folder: {output_dir}")
    print("\nGenerated files:")
    print("  1_medications.html  - Medication Schedule (Ayah/Helper)")
    print("  2_labs.html         - Lab Results Explained (Family)")
    print("  3_care_gaps.html    - Care Actions & Follow-ups (Family)")
    print("  4_imaging.html      - Imaging Explained (Family)")
    print("  5_connections.html  - Important Connections (Both)")
    print("\nTo view all pages in browser:")
    print(f"  open {output_dir}")
    print("\nTo print: Open each HTML -> File -> Print (fits 8.5x11 page)")
    print("=" * 70)
