"""
Complex Patient Demo: Showcasing MedGemma's Medical Reasoning

This demo processes a complex patient case (Dadu - 80s male with diabetes,
CHF, AFib, CKD) to demonstrate:

1. Medical Knowledge - Understanding drug mechanisms and interactions
2. Safety Awareness - Highlighting critical warnings and contraindications
3. Cross-Medication Intelligence - Connecting related medications
4. Plain Language Translation - Making complex info caregiver-friendly

Run with:
    PYTHONPATH=src .venv/bin/python -m caremap.complex_patient_demo
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .llm_client import MedGemmaClient
from .medication_interpretation import (
    interpret_medication_v3_grounded,
    MED_V3_OUT_KEYS,
)


def load_patient_data() -> Dict[str, Any]:
    """Load the golden complex patient data."""
    project_root = Path(__file__).parent.parent.parent
    golden_file = project_root / "examples" / "golden_patient_complex.json"
    with open(golden_file) as f:
        return json.load(f)


def analyze_medication_connections(medications: List[Dict]) -> Dict[str, List[str]]:
    """
    Analyze connections between medications based on clinical knowledge.

    This is rule-based analysis that MedGemma's interpretations should reflect.
    """
    connections = {
        "potassium_balance": {
            "description": "Furosemide lowers potassium, Lisinopril raises it, Potassium Chloride supplements",
            "medications": ["Furosemide", "Potassium Chloride", "Lisinopril"],
        },
        "warfarin_safety": {
            "description": "Warfarin requires avoiding NSAIDs; Acetaminophen is the safe alternative",
            "medications": ["Warfarin", "Acetaminophen"],
        },
        "kidney_sensitive": {
            "description": "Patient has CKD - Metformin requires kidney monitoring",
            "medications": ["Metformin", "Lisinopril"],
        },
        "heart_failure_trio": {
            "description": "CHF management: diuretic + beta-blocker + ACE inhibitor",
            "medications": ["Furosemide", "Carvedilol", "Lisinopril"],
        },
        "timing_critical": {
            "description": "Levothyroxine must be taken first, alone, on empty stomach",
            "medications": ["Levothyroxine"],
        },
    }
    return connections


def print_patient_summary(data: Dict[str, Any]) -> None:
    """Print a summary of the patient."""
    patient = data["patient"]
    print(f"\n{'='*70}")
    print(f"PATIENT: {patient['nickname']} ({patient['age_range']} {patient['sex']})")
    print(f"{'='*70}")
    print("CONDITIONS:")
    for condition in patient["conditions_display"]:
        print(f"  • {condition}")
    print(f"\nMEDICATIONS: {len(data['medications'])} active")
    print(f"LAB RESULTS: {len(data['results'])} recent")
    print(f"CARE GAPS: {len(data['care_gaps'])} pending")


def print_medication_connections(connections: Dict) -> None:
    """Print the medication connection analysis."""
    print(f"\n{'='*70}")
    print("MEDICATION CONNECTIONS (What MedGemma should understand):")
    print(f"{'='*70}")
    for key, info in connections.items():
        print(f"\n📎 {key.upper().replace('_', ' ')}")
        print(f"   {info['description']}")
        print(f"   Medications: {', '.join(info['medications'])}")


def process_all_medications(
    client: MedGemmaClient,
    medications: List[Dict],
) -> List[Dict[str, Any]]:
    """Process all medications through MedGemma V3."""
    results = []

    for i, med in enumerate(medications, 1):
        print(f"\n{'─'*70}")
        print(f"[{i}/{len(medications)}] Processing: {med['medication_name']}")
        print(f"{'─'*70}")

        # Show input
        print(f"  sig_text: {med['sig_text']}")
        print(f"  clinician_notes: {med['clinician_notes']}")
        print(f"  interaction_notes: {med['interaction_notes']}")

        # Process with V3 grounded
        try:
            result, raw = interpret_medication_v3_grounded(
                client=client,
                medication_name=med["medication_name"],
                sig_text=med["sig_text"],
                clinician_notes=med["clinician_notes"],
                interaction_notes=med["interaction_notes"],
                debug=False,
            )

            if "raw_response" in result:
                print(f"\n  ⚠️ JSON parsing failed, raw output:")
                print(f"  {raw[:200]}...")
                results.append({"medication": med["medication_name"], "error": "parse_failed", "raw": raw})
            else:
                print(f"\n  ✅ MedGemma Output:")
                print(f"  what_this_does: {result.get('what_this_does', 'N/A')[:80]}...")
                print(f"  watch_out_for: {result.get('watch_out_for', 'N/A')[:80]}...")
                results.append(result)

        except Exception as e:
            print(f"\n  ❌ Error: {e}")
            results.append({"medication": med["medication_name"], "error": str(e)})

    return results


def validate_safety_coverage(
    results: List[Dict],
    medications: List[Dict],
) -> Dict[str, Any]:
    """
    Validate that MedGemma captured critical safety information.

    Returns a report of what was captured vs. missed.
    """
    safety_checks = [
        {
            "medication": "Metformin",
            "critical_info": ["kidney", "ct scan", "contrast"],
            "description": "Kidney monitoring + CT scan hold",
        },
        {
            "medication": "Warfarin",
            "critical_info": ["nsaid", "ibuprofen", "aspirin", "leafy", "vitamin k", "inr"],
            "description": "NSAID danger + vitamin K consistency",
        },
        {
            "medication": "Furosemide",
            "critical_info": ["potassium", "weigh", "weight"],
            "description": "Potassium loss + daily weights",
        },
        {
            "medication": "Potassium Chloride",
            "critical_info": ["lasix", "furosemide", "food", "crush"],
            "description": "Connection to Lasix + administration",
        },
        {
            "medication": "Carvedilol",
            "critical_info": ["dizz", "slow", "stop", "sudden"],
            "description": "Dizziness + don't stop suddenly",
        },
        {
            "medication": "Lisinopril",
            "critical_info": ["cough", "potassium", "kidney"],
            "description": "Dry cough + potassium effect",
        },
        {
            "medication": "Levothyroxine",
            "critical_info": ["empty", "stomach", "calcium", "iron", "separate", "hour"],
            "description": "Empty stomach + separate from minerals",
        },
        {
            "medication": "Acetaminophen",
            "critical_info": ["3000", "ibuprofen", "nsaid", "aspirin", "warfarin"],
            "description": "Max dose + safe with warfarin + avoid NSAIDs",
        },
    ]

    report = {"passed": [], "partial": [], "failed": []}

    for check in safety_checks:
        med_name = check["medication"]

        # Find the result for this medication
        result = next((r for r in results if r.get("medication") == med_name), None)

        if not result or "error" in result:
            report["failed"].append({
                "medication": med_name,
                "reason": "Processing error",
                "expected": check["description"],
            })
            continue

        # Check if critical info is present in watch_out_for
        watch_out = result.get("watch_out_for", "").lower()
        what_does = result.get("what_this_does", "").lower()
        full_text = watch_out + " " + what_does

        found = [term for term in check["critical_info"] if term in full_text]
        missing = [term for term in check["critical_info"] if term not in full_text]

        coverage = len(found) / len(check["critical_info"])

        if coverage >= 0.5:
            report["passed"].append({
                "medication": med_name,
                "coverage": f"{coverage*100:.0f}%",
                "found": found,
                "expected": check["description"],
            })
        elif coverage > 0:
            report["partial"].append({
                "medication": med_name,
                "coverage": f"{coverage*100:.0f}%",
                "found": found,
                "missing": missing,
                "expected": check["description"],
            })
        else:
            report["failed"].append({
                "medication": med_name,
                "coverage": "0%",
                "missing": missing,
                "expected": check["description"],
            })

    return report


def print_safety_report(report: Dict[str, Any]) -> None:
    """Print the safety validation report."""
    print(f"\n{'='*70}")
    print("SAFETY VALIDATION REPORT")
    print(f"{'='*70}")

    total = len(report["passed"]) + len(report["partial"]) + len(report["failed"])

    print(f"\n✅ PASSED ({len(report['passed'])}/{total}):")
    for item in report["passed"]:
        print(f"   {item['medication']}: {item['coverage']} - {item['expected']}")

    if report["partial"]:
        print(f"\n⚠️ PARTIAL ({len(report['partial'])}/{total}):")
        for item in report["partial"]:
            print(f"   {item['medication']}: {item['coverage']}")
            print(f"      Found: {item['found']}")
            print(f"      Missing: {item['missing']}")

    if report["failed"]:
        print(f"\n❌ FAILED ({len(report['failed'])}/{total}):")
        for item in report["failed"]:
            print(f"   {item['medication']}: {item.get('reason', 'Missing info')}")
            print(f"      Expected: {item['expected']}")

    # Summary score
    score = (len(report["passed"]) + 0.5 * len(report["partial"])) / total * 100
    print(f"\n{'='*70}")
    print(f"SAFETY SCORE: {score:.0f}%")
    print(f"{'='*70}")


def generate_fridge_sheet(
    patient: Dict,
    results: List[Dict],
) -> str:
    """Generate a text-based fridge sheet from the results."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"MEDICATION FRIDGE SHEET FOR {patient['nickname'].upper()}")
    lines.append("=" * 60)
    lines.append("")

    for result in results:
        if "error" in result:
            continue

        lines.append(f"💊 {result.get('medication', 'Unknown')}")
        lines.append(f"   What it does: {result.get('what_this_does', 'N/A')}")
        lines.append(f"   How to give: {result.get('how_to_give', 'N/A')}")
        if result.get('watch_out_for'):
            lines.append(f"   ⚠️ Watch out: {result.get('watch_out_for')}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("Always contact your care team with questions!")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """Main demo entry point."""
    print("\n" + "🏥 " * 25)
    print("COMPLEX PATIENT DEMO: MedGemma Medical Reasoning Showcase")
    print("🏥 " * 25)

    # Load patient data
    data = load_patient_data()
    print_patient_summary(data)

    # Analyze medication connections
    connections = analyze_medication_connections(data["medications"])
    print_medication_connections(connections)

    # Initialize MedGemma
    print(f"\n{'='*70}")
    print("Initializing MedGemma client...")
    print(f"{'='*70}")
    client = MedGemmaClient()

    # Process all medications
    print(f"\n{'='*70}")
    print("PROCESSING ALL 8 MEDICATIONS WITH MedGemma V3 (Grounded)")
    print(f"{'='*70}")
    results = process_all_medications(client, data["medications"])

    # Validate safety coverage
    report = validate_safety_coverage(results, data["medications"])
    print_safety_report(report)

    # Generate fridge sheet
    print(f"\n{'='*70}")
    print("GENERATED FRIDGE SHEET")
    print(f"{'='*70}")
    fridge_sheet = generate_fridge_sheet(data["patient"], results)
    print(fridge_sheet)

    # Save results
    output_dir = Path(__file__).parent.parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "complex_patient_results.json", "w") as f:
        json.dump({
            "patient": data["patient"],
            "medications_processed": len(results),
            "safety_report": report,
            "interpretations": results,
        }, f, indent=2)

    print(f"\n✅ Results saved to outputs/complex_patient_results.json")


if __name__ == "__main__":
    main()
