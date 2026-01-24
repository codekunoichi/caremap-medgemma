"""
Pydantic schemas for imaging interpretation outputs.

V1: Constrained output (original spec)
V2: Richer output (experimental/grounded)
"""
from typing import List
from pydantic import BaseModel, Field


class ImagingOutputV1(BaseModel):
    """
    V1 Imaging output schema (constrained).

    Original specification with strict sentence limits.
    Keys: study_type, what_was_done, key_finding, what_to_ask_doctor
    """

    study_type: str = Field(
        description="The type of imaging study (e.g., 'Chest CT', 'Brain MRI')"
    )
    what_was_done: str = Field(
        description="One sentence explaining what this scan does in plain language",
        max_length=150,
    )
    key_finding: str = Field(
        description="Up to 2-3 sentences describing the main finding in plain language. "
        "No medical jargon. No specific measurements.",
        max_length=400,
    )
    what_to_ask_doctor: str = Field(
        description="One question the caregiver should ask their doctor about this result",
        max_length=150,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "study_type": "Chest X-ray",
                "what_was_done": "A picture was taken of the lungs and heart using X-rays.",
                "key_finding": "The scan shows a cloudy area in the lower part of the right lung. "
                "This is something the doctor will want to monitor.",
                "what_to_ask_doctor": "What is causing the cloudy area in my lung?",
            }
        }


class ImagingOutputV2(BaseModel):
    """
    V2 Imaging output schema (experimental/grounded).

    Richer output without strict sentence limits.
    Keys: study_type, what_this_scan_does, what_was_found, what_this_means, questions_for_doctor
    """

    study_type: str = Field(
        description="The type of imaging study with plain language explanation "
        "(e.g., 'Chest CT (detailed X-ray pictures of the chest)')"
    )
    what_this_scan_does: str = Field(
        description="Plain language explanation of what this type of scan shows and "
        "why doctors order it. Should help caregiver understand the purpose.",
    )
    what_was_found: str = Field(
        description="Description of the findings in plain language. "
        "Replace medical terms: 'nodule' -> 'spot', 'effusion' -> 'fluid'. "
        "Never include specific measurements like '8mm'. "
        "Never use the word 'cancer'.",
    )
    what_this_means: str = Field(
        description="Interpretation of what the findings mean for the patient's care. "
        "Include the flag status (normal/needs_follow_up/urgent) in context. "
        "Focus on next steps and what the caregiver should watch for.",
    )
    questions_for_doctor: List[str] = Field(
        description="2-3 specific questions the caregiver should ask their doctor "
        "about these findings. Each question should be actionable.",
        min_length=1,
        max_length=4,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "study_type": "Chest CT (detailed X-ray pictures of the chest)",
                "what_this_scan_does": "A CT scan uses X-rays from many angles to create "
                "detailed pictures of the inside of the chest. It helps doctors see the "
                "lungs, heart, and blood vessels more clearly than a regular X-ray.",
                "what_was_found": "The scan found a small spot in the lower part of the right lung. "
                "The heart appears slightly larger than usual. The blood vessels show some "
                "wear and tear that is common with age.",
                "what_this_means": "Needs follow-up - The doctor will want to take another look "
                "at the spot in a few months to make sure it stays the same size. The heart "
                "changes fit with the known heart condition. No urgent action is needed right now.",
                "questions_for_doctor": [
                    "What could be causing the spot in the lung?",
                    "When should we do the follow-up scan?",
                    "Are there any warning signs I should watch for before then?",
                ],
            }
        }


class ImagingInput(BaseModel):
    """Input schema for imaging interpretation."""

    study_type: str = Field(description="Type of imaging study")
    report_text: str = Field(description="Radiology report text")
    flag: str = Field(
        default="normal",
        description="Status flag: normal, needs_follow_up, or urgent",
    )
