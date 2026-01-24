"""
Pydantic schemas for care gap interpretation outputs.

V1: Constrained output (original spec)
V2: Richer output (experimental/grounded)
"""
from typing import Literal
from pydantic import BaseModel, Field


class CareGapOutputV1(BaseModel):
    """
    V1 Care Gap output schema (constrained).

    Original specification with strict sentence limits.
    Keys: time_bucket, action_item, next_step
    """

    time_bucket: Literal["Today", "This Week", "Later"] = Field(
        description="Urgency category: Today, This Week, or Later"
    )
    action_item: str = Field(
        description="One sentence describing what needs to be done. "
        "Keep it short and scannable for a busy caregiver.",
        max_length=150,
    )
    next_step: str = Field(
        description="Concrete next step: who to call, what to schedule, etc.",
        max_length=200,
    )

    class Config:
        json_schema_extra = {
            "example": {
                "time_bucket": "This Week",
                "action_item": "Schedule the annual eye exam for diabetes.",
                "next_step": "Call Dr. Smith's office at 555-1234 to make an appointment.",
            }
        }


class CareGapOutputV2(BaseModel):
    """
    V2 Care Gap output schema (experimental/grounded).

    Richer output without strict sentence limits.
    Keys: care_item, time_bucket, why_this_matters, what_to_do, how_to_prepare
    """

    care_item: str = Field(
        description="Plain language name for the care gap item "
        "(e.g., 'Eye Exam for Diabetes' instead of 'Diabetic Retinopathy Screening')"
    )
    time_bucket: Literal["Today", "This Week", "Later"] = Field(
        description="Urgency category based on clinical priority"
    )
    why_this_matters: str = Field(
        description="Plain language explanation of why this care item is important. "
        "Connect to the patient's conditions. Help caregiver understand the 'why' "
        "so they're motivated to follow through.",
    )
    what_to_do: str = Field(
        description="Clear, actionable instructions for the caregiver. "
        "Include who to contact, what to ask for, and any reference numbers if available.",
    )
    how_to_prepare: str = Field(
        description="Practical preparation tips: what to bring, what to expect, "
        "any special instructions (fasting, medication changes, etc.). "
        "Reduce anxiety by explaining what will happen.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "care_item": "Eye Exam for Diabetes",
                "time_bucket": "This Week",
                "why_this_matters": "Diabetes can affect the small blood vessels in the eyes "
                "over time. An annual eye exam helps catch any changes early, when they're "
                "easiest to treat. This is especially important because Dadu has had diabetes "
                "for several years.",
                "what_to_do": "Call Dr. Smith's office at 555-1234 to schedule a dilated eye exam. "
                "Mention that this is for the annual diabetes eye screening. If they can't see you "
                "this week, ask to be put on a cancellation list.",
                "how_to_prepare": "Bring sunglasses - the eye drops used to dilate the pupils make "
                "eyes sensitive to light for a few hours. Dadu shouldn't drive after the appointment. "
                "Bring the current medication list to share with the eye doctor.",
            }
        }


class CareGapInput(BaseModel):
    """Input schema for care gap interpretation."""

    item_text: str = Field(description="Description of the care gap item")
    next_step: str = Field(description="Concrete instruction from source record")
    time_bucket: str = Field(
        description="Pre-assigned urgency: Today, This Week, or Later"
    )
    source: str = Field(
        default="", description="Optional source of the care gap (e.g., 'Annual wellness visit')"
    )
