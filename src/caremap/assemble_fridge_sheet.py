from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List

from .caregap_interpretation import interpret_caregap
from .lab_interpretation import interpret_lab
from .llm_client import MedGemmaClient
from .medication_interpretation import interpret_medication


@dataclass
class BuildLimits:
    """
    Hard limits to prevent feature bloat and keep the one-page fridge sheet readable.
    """
    max_meds: int = 8
    max_labs: int = 3
    max_actions_today: int = 2
    max_actions_week: int = 2
    max_actions_later: int = 1


def _extract_when_to_give(med: Dict[str, Any]) -> str:
    """
    Extract timing information from v1.1 EHR-aligned medication entry.

    Priority:
      1. timing (caregiver-friendly if available)
      2. sig_text (full signature from EHR)
      3. Empty string (will become "Not specified — confirm with care team")
    """
    timing = str(med.get("timing", "")).strip()
    if timing:
        return timing

    sig_text = str(med.get("sig_text", "")).strip()
    if sig_text:
        return sig_text

    return ""


def build_fridge_sheet(
    canonical_patient: Dict[str, Any],
    client: MedGemmaClient,
    limits: BuildLimits | None = None,
) -> Dict[str, Any]:
    """
    Build a cohesive fridge-sheet JSON from a Canonical patient record (v1.1 EHR-aligned).

    Expected canonical inputs (v1.1 schema):
      - meta: { source?, generated_on?, language? }
      - patient: { nickname?, age_range?, sex?, conditions_display? }
      - medications: list[ { medication_name, sig_text?, timing?, clinician_notes?, interaction_notes? } ]
      - results: list[ { test_name, meaning_category, flag?, source_note? } ]
      - care_gaps: list[ { item_text, next_step, time_bucket } ]
      - contacts: { clinic_name?, clinic_phone?, pharmacy_name?, pharmacy_phone? }

    Notes:
      - We keep selection logic deterministic and conservative.
      - Relative buckets (Today/This Week/Later) are anchored by meta.generated_on at render time.
      - Missing timing defaults to "Not specified — confirm with care team" downstream.
    """
    limits = limits or BuildLimits()

    # Extract sections from canonical v1.1 schema
    meta_in = canonical_patient.get("meta", {}) or {}
    patient_in = canonical_patient.get("patient", {}) or {}
    meds_in = canonical_patient.get("medications", []) or []
    results_in = canonical_patient.get("results", []) or []
    care_in = canonical_patient.get("care_gaps", []) or []
    contacts_in = canonical_patient.get("contacts", {}) or {}

    # Process medications (limit to max_meds)
    medications: List[Dict[str, Any]] = []
    for m in meds_in[: limits.max_meds]:
        medications.append(
            interpret_medication(
                client=client,
                medication_name=str(m.get("medication_name", "")).strip(),
                when_to_give=_extract_when_to_give(m),
                clinician_notes=str(m.get("clinician_notes", "")).strip(),
                interaction_notes=str(m.get("interaction_notes", "")).strip(),
            )
        )

    # Process lab results (limit to max_labs)
    labs: List[Dict[str, Any]] = []
    for r in results_in[: limits.max_labs]:
        labs.append(
            interpret_lab(
                client=client,
                test_name=str(r.get("test_name", "")).strip(),
                meaning_category=str(r.get("meaning_category", "")).strip(),
                source_note=str(r.get("source_note", "")).strip(),
            )
        )

    # Process care gaps / actions by time bucket
    actions: Dict[str, List[Dict[str, Any]]] = {"Today": [], "This Week": [], "Later": []}
    for c in care_in:
        bucket = str(c.get("time_bucket", "")).strip()
        if bucket not in actions:
            continue  # ignore unknown bucket

        # Enforce per-bucket caps
        if bucket == "Today" and len(actions[bucket]) >= limits.max_actions_today:
            continue
        if bucket == "This Week" and len(actions[bucket]) >= limits.max_actions_week:
            continue
        if bucket == "Later" and len(actions[bucket]) >= limits.max_actions_later:
            continue

        actions[bucket].append(
            interpret_caregap(
                client=client,
                item_text=str(c.get("item_text", "")).strip(),
                next_step=str(c.get("next_step", "")).strip(),
                time_bucket=bucket,
            )
        )

    # Build output structure
    out: Dict[str, Any] = {
        "meta": {
            "generated_on": meta_in.get("generated_on") or date.today().isoformat(),
            "language": meta_in.get("language", "en"),
            "source": meta_in.get("source", ""),
        },
        "patient": {
            "nickname": patient_in.get("nickname", ""),
            "age_range": patient_in.get("age_range", ""),
            "conditions": patient_in.get("conditions_display", [])[:3],  # Max 3 conditions
        },
        "medications": medications,
        "labs": labs,
        "actions": actions,
        "contacts": {
            "clinic": {
                "name": contacts_in.get("clinic_name", "") or "Not available",
                "phone": contacts_in.get("clinic_phone", "") or "Not available",
            },
            "pharmacy": {
                "name": contacts_in.get("pharmacy_name", "") or "Not available",
                "phone": contacts_in.get("pharmacy_phone", "") or "Not available",
            },
        },
    }
    return out
