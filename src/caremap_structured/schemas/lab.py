"""
Pydantic schemas for lab interpretation outputs.

V1: Constrained output (original spec)
V2: Richer output (experimental/grounded)
"""
from typing import List
from pydantic import BaseModel, Field


class LabOutputV1(BaseModel):
    """
    V1 Lab output schema (constrained).

    Original specification with strict sentence limits.
    Keys: what_was_checked, what_it_means, what_to_ask_doctor
    """

    what_was_checked: str = Field(
        description="One sentence explaining what this lab test measures in plain language",
        max_length=150,
    )
    what_it_means: str = Field(
        description="Plain language explanation of what the result category means. "
        "No specific numeric values. Use meaning_category (Normal/Slightly off/Needs follow-up).",
        max_length=300,
    )
    what_to_ask_doctor: str = Field(
        description="One question the caregiver should ask their doctor about this result",
        max_length=150,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "what_was_checked": "This test measures how well the kidneys are filtering waste from the blood.",
                "what_it_means": "The result is slightly off, which means the kidneys may not be working as well as they should. The doctor will want to keep an eye on this.",
                "what_to_ask_doctor": "What can we do to help protect the kidneys?",
            }
        }


class LabOutputV2(BaseModel):
    """
    V2 Lab output schema (experimental/grounded).

    Richer output without strict sentence limits.
    Keys: test_name, what_this_test_measures, why_this_matters, current_status, questions_for_doctor
    """

    test_name: str = Field(
        description="Plain language name for the test (e.g., 'Kidney Function Test' instead of 'eGFR')"
    )
    what_this_test_measures: str = Field(
        description="Plain language explanation of what this test checks and why doctors order it. "
        "Avoid medical abbreviations. Explain in terms of body function.",
    )
    why_this_matters: str = Field(
        description="Explanation of why this test is important for this patient specifically. "
        "Connect to their conditions or medications if relevant. "
        "Help caregiver understand the clinical significance.",
    )
    current_status: str = Field(
        description="Plain language interpretation of the current result category. "
        "Use the meaning_category (Normal/Slightly off/Needs follow-up) to guide the tone. "
        "Never include specific numeric values. "
        "Explain what this means for daily care and what to watch for.",
    )
    questions_for_doctor: List[str] = Field(
        description="2-3 specific questions the caregiver should ask their doctor "
        "about this lab result. Focus on actionable next steps.",
        min_length=1,
        max_length=4,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "test_name": "Blood Sugar Control Test (HbA1c)",
                "what_this_test_measures": "This test shows how well blood sugar has been "
                "controlled over the past 2-3 months. Unlike a daily blood sugar check, "
                "this gives a bigger picture of diabetes management.",
                "why_this_matters": "For someone with diabetes taking Metformin, this test "
                "helps the doctor know if the current treatment is working well enough "
                "or if changes are needed.",
                "current_status": "The result is slightly off - blood sugar control could be "
                "a bit better. This doesn't mean anything is wrong right now, but the doctor "
                "may want to discuss diet, exercise, or medication adjustments.",
                "questions_for_doctor": [
                    "What changes can we make to improve blood sugar control?",
                    "Should we adjust any medications based on this result?",
                    "How often should we repeat this test?",
                ],
            }
        }


class LabInput(BaseModel):
    """Input schema for lab interpretation."""

    test_name: str = Field(description="Name of the lab test")
    meaning_category: str = Field(
        description="Pre-computed category: Normal, Slightly off, or Needs follow-up"
    )
    source_note: str = Field(
        default="", description="Optional non-numeric context from the record"
    )
