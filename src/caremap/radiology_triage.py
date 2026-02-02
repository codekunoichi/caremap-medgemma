"""
Radiology Triage Module - AI-assisted X-ray prioritization.

Uses MedGemma's multimodal capabilities to analyze chest X-rays
and assign priority levels for radiologist review.
"""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .llm_client import MedGemmaClient
from .prompt_loader import load_prompt


@dataclass
class TriageResult:
    """Result of triage analysis for a single image."""
    image_id: str
    findings: list[str]
    primary_impression: str
    priority: str  # STAT, SOON, ROUTINE
    priority_reason: str
    confidence: float
    patient_age: int
    patient_gender: str
    ground_truth_findings: Optional[str] = None


def extract_json_from_response(text: str) -> dict:
    """Extract JSON object from LLM response."""
    # Try to find JSON block
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Return default if parsing fails
    return {
        "findings": ["Unable to parse findings"],
        "primary_impression": "Analysis incomplete",
        "priority": "STAT",  # Default to highest priority on failure
        "priority_reason": "Unable to complete analysis - defaulting to highest priority",
        "confidence": 0.0
    }


def analyze_xray(
    client: MedGemmaClient,
    image_path: str,
    patient_age: int,
    patient_gender: str,
) -> dict:
    """
    Analyze a single chest X-ray image.

    Args:
        client: MedGemma client with multimodal support
        image_path: Path to the X-ray image
        patient_age: Patient age in years
        patient_gender: M or F

    Returns:
        Dictionary with findings, priority, and confidence
    """
    prompt = load_prompt(
        "radiology_triage.txt",
        PATIENT_AGE=str(patient_age),
        PATIENT_GENDER="Male" if patient_gender == "M" else "Female"
    )

    response = client.generate_with_images(prompt, images=[image_path])
    return extract_json_from_response(response)


def triage_batch(
    client: MedGemmaClient,
    manifest_path: str,
    images_base_dir: str,
    progress_callback=None
) -> list[TriageResult]:
    """
    Process a batch of images from a manifest file.

    Args:
        client: MedGemma client with multimodal support
        manifest_path: Path to CSV with image_id, priority, findings, patient_age, patient_gender
        images_base_dir: Base directory containing stat/, soon/, routine/ subdirs
        progress_callback: Optional callback(current, total, image_id) for progress updates

    Returns:
        List of TriageResult objects sorted by priority
    """
    import pandas as pd

    manifest = pd.read_csv(manifest_path)
    results = []
    total = len(manifest)

    for idx, row in manifest.iterrows():
        image_id = row['image_id']
        ground_truth_priority = row['priority'].upper()
        ground_truth_findings = row['findings']

        # Find image in priority subfolder
        image_path = Path(images_base_dir) / ground_truth_priority.lower() / image_id

        if not image_path.exists():
            # Try finding in any subfolder
            for subdir in ['stat', 'soon', 'routine']:
                alt_path = Path(images_base_dir) / subdir / image_id
                if alt_path.exists():
                    image_path = alt_path
                    break

        if progress_callback:
            progress_callback(idx + 1, total, image_id)

        if not image_path.exists():
            print(f"Warning: Image not found: {image_path}")
            continue

        try:
            analysis = analyze_xray(
                client,
                str(image_path),
                int(row['patient_age']),
                row['patient_gender']
            )

            results.append(TriageResult(
                image_id=image_id,
                findings=analysis.get('findings', []),
                primary_impression=analysis.get('primary_impression', ''),
                priority=analysis.get('priority', 'STAT'),
                priority_reason=analysis.get('priority_reason', ''),
                confidence=analysis.get('confidence', 0.0),
                patient_age=int(row['patient_age']),
                patient_gender=row['patient_gender'],
                ground_truth_findings=ground_truth_findings
            ))
        except Exception as e:
            print(f"Error analyzing {image_id}: {e}")
            results.append(TriageResult(
                image_id=image_id,
                findings=["Error during analysis"],
                primary_impression=f"Analysis failed: {str(e)}",
                priority="STAT",  # Default to highest on error
                priority_reason="Analysis error - defaulting to highest priority",
                confidence=0.0,
                patient_age=int(row['patient_age']),
                patient_gender=row['patient_gender'],
                ground_truth_findings=ground_truth_findings
            ))

    # Sort by priority: STAT first, then SOON, then ROUTINE
    priority_order = {'STAT': 0, 'SOON': 1, 'ROUTINE': 2}
    results.sort(key=lambda r: (priority_order.get(r.priority, 0), -r.confidence))

    return results


def format_triage_queue(results: list[TriageResult]) -> str:
    """Format triage results as a readable queue."""
    output = []

    # Group by priority
    stat = [r for r in results if r.priority == 'STAT']
    soon = [r for r in results if r.priority == 'SOON']
    routine = [r for r in results if r.priority == 'ROUTINE']

    output.append("=" * 60)
    output.append(f"RADIOLOGY TRIAGE QUEUE - {len(results)} Studies")
    output.append("=" * 60)

    output.append(f"\n🔴 STAT - Critical ({len(stat)} studies)")
    output.append("-" * 40)
    for r in stat:
        output.append(f"  {r.image_id} | {r.patient_age}{r.patient_gender}")
        output.append(f"    {r.primary_impression}")
        output.append(f"    Confidence: {r.confidence:.0%}")

    output.append(f"\n🟡 SOON - Abnormal ({len(soon)} studies)")
    output.append("-" * 40)
    for r in soon:
        output.append(f"  {r.image_id} | {r.patient_age}{r.patient_gender}")
        output.append(f"    {r.primary_impression}")
        output.append(f"    Confidence: {r.confidence:.0%}")

    output.append(f"\n🟢 ROUTINE - Normal ({len(routine)} studies)")
    output.append("-" * 40)
    for r in routine:
        output.append(f"  {r.image_id} | {r.patient_age}{r.patient_gender}")
        output.append(f"    {r.primary_impression}")
        output.append(f"    Confidence: {r.confidence:.0%}")

    return "\n".join(output)


if __name__ == "__main__":
    # Demo: analyze a single image
    from caremap import MedGemmaClient

    client = MedGemmaClient(enable_multimodal=True)

    # Test on first STAT image
    image_path = "data/nih_chest_xray/demo_images/stat/00000032_001.png"
    result = analyze_xray(client, image_path, 55, "F")

    print("=" * 60)
    print("SINGLE IMAGE ANALYSIS")
    print("=" * 60)
    print(json.dumps(result, indent=2))
