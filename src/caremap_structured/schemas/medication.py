"""
Pydantic schemas for medication interpretation outputs.

V1: Constrained output (original spec)
V2: Richer output (experimental/grounded)
"""
from typing import Optional
from pydantic import BaseModel, Field


class MedicationOutputV1(BaseModel):
    """
    V1 Medication output schema (constrained).

    Original specification with strict sentence limits.
    Keys: medication, why_it_matters, when_to_give, important_note
    """

    medication: str = Field(
        description="The medication name (preserved verbatim from input)"
    )
    why_it_matters: str = Field(
        description="One sentence explaining why this medication is important",
        max_length=200,
    )
    when_to_give: str = Field(
        description="Timing information (preserved verbatim from input)"
    )
    important_note: Optional[str] = Field(
        default=None,
        description="Optional: One sentence about something important to watch for",
        max_length=200,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "medication": "Metformin",
                "why_it_matters": "This medicine helps control blood sugar levels.",
                "when_to_give": "8 AM, 6 PM",
                "important_note": "Take with food to avoid stomach upset.",
            }
        }


class MedicationOutputV2(BaseModel):
    """
    V2 Medication output schema (experimental/grounded).

    Richer output without strict sentence limits.
    Keys: medication, what_this_does, how_to_give, watch_out_for
    """

    medication: str = Field(
        description="The medication name (preserved verbatim from input)"
    )
    what_this_does: str = Field(
        description="Plain language explanation of what this medication does and why it's prescribed. "
        "Should be understandable by a 6th grader. No medical jargon.",
    )
    how_to_give: str = Field(
        description="Clear instructions on how to administer: timing, with/without food, "
        "any special preparation. Include the when_to_give timing.",
    )
    watch_out_for: str = Field(
        description="Safety warnings, drug interactions, and side effects to monitor. "
        "Include what to do if problems occur (e.g., 'call the doctor if...').",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "medication": "Warfarin",
                "what_this_does": "This blood thinner helps prevent dangerous blood clots "
                "that could cause a stroke. It's especially important because of the "
                "irregular heartbeat (AFib).",
                "how_to_give": "Give one 5mg tablet by mouth every evening at 6 PM. "
                "Try to give it at the same time each day. Can be taken with or without food.",
                "watch_out_for": "Never give aspirin, ibuprofen, or other pain medicines "
                "without asking the doctor first - they can cause dangerous bleeding. "
                "Watch for unusual bruising, blood in urine or stool, or bleeding gums. "
                "Keep vitamin K intake consistent (leafy greens). Call the doctor immediately "
                "if you notice any signs of bleeding.",
            }
        }


class MedicationInput(BaseModel):
    """Input schema for medication interpretation."""

    medication_name: str = Field(description="Name of the medication")
    sig_text: str = Field(description="Prescription instructions (sig)")
    clinician_notes: str = Field(
        default="", description="Additional notes from clinician"
    )
    interaction_notes: str = Field(
        default="", description="Drug interaction warnings"
    )
