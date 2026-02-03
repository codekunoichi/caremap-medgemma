"""
HL7 ORU Message Triage Module - AI-assisted clinical result prioritization.

Uses MedGemma to analyze incoming HL7 ORU messages (lab results, radiology reports)
and assign priority levels for clinician review.
"""

import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .llm_client import MedGemmaClient
from .prompt_loader import load_prompt, fill_prompt


@dataclass
class HL7TriageResult:
    """Result of triage analysis for a single ORU message."""
    message_id: str
    message_type: str
    patient_id: str
    priority: str  # STAT, SOON, ROUTINE
    priority_reason: str
    key_findings: list[str]
    recommended_action: str
    confidence: float
    ground_truth_priority: Optional[str] = None


def extract_json_from_response(text: str) -> dict:
    """Extract JSON object from LLM response."""
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Return default if parsing fails
    return {
        "priority": "STAT",  # Default to highest priority on failure
        "priority_reason": "Unable to parse response - defaulting to highest priority",
        "key_findings": ["Analysis incomplete"],
        "recommended_action": "Manual review required",
        "confidence": 0.0
    }


def format_observations(observations: list[dict]) -> str:
    """Format observations list into readable text for the prompt."""
    lines = []
    for obs in observations:
        if obs.get('value_type') == 'TEXT':
            # Radiology/text result
            lines.append(f"- {obs['test_name']}: {obs['value']}")
        else:
            # Numeric lab result
            flag = f" [{obs['abnormal_flag']}]" if obs.get('abnormal_flag') else ""
            ref = f" (ref: {obs['reference_range']})" if obs.get('reference_range') else ""
            lines.append(f"- {obs['test_name']}: {obs['value']} {obs.get('units', '')}{ref}{flag}")

    return "\n".join(lines)


def triage_oru_message(
    client: MedGemmaClient,
    message: dict,
) -> dict:
    """
    Triage a single ORU message.

    Args:
        client: MedGemma client
        message: ORU message dict with observations

    Returns:
        Dictionary with priority, findings, and recommendations
    """
    patient = message.get('patient', {})
    observations_text = format_observations(message.get('observations', []))

    template = load_prompt("hl7_oru_triage.txt")
    prompt = fill_prompt(template, {
        "MESSAGE_TYPE": message.get('message_type', 'LAB'),
        "PATIENT_AGE": str(patient.get('age', 'Unknown')),
        "PATIENT_GENDER": "Male" if patient.get('gender') == "M" else "Female",
        "CLINICAL_CONTEXT": message.get('clinical_context', 'Not provided'),
        "OBSERVATIONS": observations_text
    })

    response = client.generate(prompt)
    return extract_json_from_response(response)


def triage_batch(
    client: MedGemmaClient,
    messages: list[dict],
    progress_callback=None
) -> list[HL7TriageResult]:
    """
    Process a batch of ORU messages.

    Args:
        client: MedGemma client
        messages: List of ORU message dicts
        progress_callback: Optional callback(current, total, message_id)

    Returns:
        List of HL7TriageResult objects sorted by priority
    """
    results = []
    total = len(messages)

    for idx, msg in enumerate(messages):
        message_id = msg.get('message_id', f'MSG-{idx}')

        if progress_callback:
            progress_callback(idx + 1, total, message_id)

        try:
            analysis = triage_oru_message(client, msg)

            results.append(HL7TriageResult(
                message_id=message_id,
                message_type=msg.get('message_type', 'LAB'),
                patient_id=msg.get('patient', {}).get('id', 'Unknown'),
                priority=analysis.get('priority', 'STAT'),
                priority_reason=analysis.get('priority_reason', ''),
                key_findings=analysis.get('key_findings', []),
                recommended_action=analysis.get('recommended_action', ''),
                confidence=analysis.get('confidence', 0.0),
                ground_truth_priority=msg.get('expected_priority')
            ))
        except Exception as e:
            print(f"Error analyzing {message_id}: {e}")
            results.append(HL7TriageResult(
                message_id=message_id,
                message_type=msg.get('message_type', 'LAB'),
                patient_id=msg.get('patient', {}).get('id', 'Unknown'),
                priority="STAT",
                priority_reason=f"Analysis error - defaulting to highest priority: {str(e)}",
                key_findings=["Error during analysis"],
                recommended_action="Manual review required",
                confidence=0.0,
                ground_truth_priority=msg.get('expected_priority')
            ))

    # Sort by priority: STAT first, then SOON, then ROUTINE
    priority_order = {'STAT': 0, 'SOON': 1, 'ROUTINE': 2}
    results.sort(key=lambda r: (priority_order.get(r.priority, 0), -r.confidence))

    return results


def format_triage_queue(results: list[HL7TriageResult]) -> str:
    """Format triage results as a readable queue."""
    output = []

    # Group by priority
    stat = [r for r in results if r.priority == 'STAT']
    soon = [r for r in results if r.priority == 'SOON']
    routine = [r for r in results if r.priority == 'ROUTINE']

    output.append("=" * 70)
    output.append(f"HL7 ORU MESSAGE TRIAGE QUEUE - {len(results)} Messages")
    output.append("=" * 70)

    output.append(f"\n🔴 STAT - Critical ({len(stat)} messages)")
    output.append("-" * 50)
    for r in stat:
        match = "✓" if r.ground_truth_priority == r.priority else "✗" if r.ground_truth_priority else ""
        output.append(f"  {match} {r.message_id} | {r.message_type} | Patient {r.patient_id}")
        output.append(f"      Reason: {r.priority_reason[:70]}...")
        output.append(f"      Action: {r.recommended_action[:70]}...")
        output.append(f"      Confidence: {r.confidence:.0%}")

    output.append(f"\n🟡 SOON - Abnormal ({len(soon)} messages)")
    output.append("-" * 50)
    for r in soon:
        match = "✓" if r.ground_truth_priority == r.priority else "✗" if r.ground_truth_priority else ""
        output.append(f"  {match} {r.message_id} | {r.message_type} | Patient {r.patient_id}")
        output.append(f"      Reason: {r.priority_reason[:70]}...")
        output.append(f"      Confidence: {r.confidence:.0%}")

    output.append(f"\n🟢 ROUTINE - Normal ({len(routine)} messages)")
    output.append("-" * 50)
    for r in routine:
        match = "✓" if r.ground_truth_priority == r.priority else "✗" if r.ground_truth_priority else ""
        output.append(f"  {match} {r.message_id} | {r.message_type} | Patient {r.patient_id}")
        output.append(f"      Reason: {r.priority_reason[:70]}...")
        output.append(f"      Confidence: {r.confidence:.0%}")

    # Calculate accuracy if ground truth available
    with_gt = [r for r in results if r.ground_truth_priority]
    if with_gt:
        correct = sum(1 for r in with_gt if r.priority == r.ground_truth_priority)
        output.append(f"\n{'='*70}")
        output.append(f"Priority Match Accuracy: {correct}/{len(with_gt)} ({correct/len(with_gt)*100:.0f}%)")

    return "\n".join(output)


def load_sample_messages(filepath: str = None) -> list[dict]:
    """Load sample ORU messages from JSON file."""
    if filepath is None:
        # Default to examples folder
        filepath = Path(__file__).parent.parent.parent / "examples" / "sample_oru_messages.json"

    with open(filepath) as f:
        data = json.load(f)

    return data.get('messages', [])


if __name__ == "__main__":
    # Demo: triage sample messages
    from caremap import MedGemmaClient

    print("Loading MedGemma...")
    client = MedGemmaClient()

    print("Loading sample ORU messages...")
    messages = load_sample_messages()
    print(f"Loaded {len(messages)} messages")

    # Triage first 5 messages as demo
    print("\nTriaging messages...")
    results = triage_batch(
        client,
        messages[:5],
        progress_callback=lambda c, t, m: print(f"  [{c}/{t}] {m}")
    )

    print("\n" + format_triage_queue(results))
