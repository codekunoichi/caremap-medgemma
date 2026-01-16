from __future__ import annotations

import json
from pathlib import Path

from caremap.llm_client import MedGemmaClient
from caremap.assemble_fridge_sheet import build_fridge_sheet


def _repo_root() -> Path:
    # src/run_demo.py -> repo root is one parent up
    return Path(__file__).resolve().parents[1]


def load_sample_patient() -> dict:
    """
    Load a sample canonical patient JSON (v1.1 EHR-aligned schema).

    Expected location:
      examples/sample_patient_01.json

    If the file does not exist, we fall back to an inline minimal sample.
    """
    sample_path = _repo_root() / "examples" / "sample_patient_01.json"
    if sample_path.exists():
        return json.loads(sample_path.read_text(encoding="utf-8"))

    # Inline fallback sample (v1.1 EHR-aligned schema)
    return {
        "meta": {
            "source": "Manual",
            "generated_on": "2026-01-15",
            "language": "en"
        },
        "patient": {
            "nickname": "Maa",
            "age_range": "70s",
            "conditions_display": ["Diabetes", "High blood pressure"]
        },
        "medications": [
            {
                "medication_name": "Metformin",
                "sig_text": "Take 1 tablet by mouth twice daily with meals",
                "timing": "morning and evening, with food",
                "clinician_notes": "",
                "interaction_notes": ""
            },
            {
                "medication_name": "Atorvastatin",
                "sig_text": "Take 1 tablet by mouth daily at bedtime",
                "timing": "at bedtime",
                "clinician_notes": "",
                "interaction_notes": ""
            }
        ],
        "results": [
            {
                "test_name": "Hemoglobin",
                "meaning_category": "Needs follow-up",
                "flag": "low",
                "source_note": "Flagged low in portal"
            }
        ],
        "care_gaps": [
            {
                "item_text": "Eye exam overdue",
                "next_step": "Call clinic to schedule",
                "time_bucket": "This Week"
            },
            {
                "item_text": "Blood work due",
                "next_step": "Schedule lab visit",
                "time_bucket": "Today"
            }
        ],
        "contacts": {
            "clinic_name": "Primary Care Clinic",
            "clinic_phone": "555-0100",
            "pharmacy_name": "Main Street Pharmacy",
            "pharmacy_phone": "555-0199"
        }
    }


def main() -> int:
    print("[CareMap] Loading MedGemma client...")
    client = MedGemmaClient(model_id="google/medgemma-4b-it", device=None)

    print("[CareMap] Loading sample canonical patient...")
    patient = load_sample_patient()

    print("[CareMap] Building fridge sheet JSON...")
    fridge = build_fridge_sheet(patient, client)

    out_dir = _repo_root() / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "fridge_sheet.json"
    out_path.write_text(json.dumps(fridge, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[CareMap] Wrote: {out_path}")
    print(json.dumps(fridge, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
