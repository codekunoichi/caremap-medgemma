"""
Structured output generators using outlines.

These generators use the outlines library to constrain MedGemma's
token generation to produce valid JSON matching our Pydantic schemas.
"""
from .structured_generator import (
    StructuredMedGemmaClient,
    generate_medication_output,
    generate_imaging_output,
    generate_lab_output,
    generate_caregap_output,
)

__all__ = [
    "StructuredMedGemmaClient",
    "generate_medication_output",
    "generate_imaging_output",
    "generate_lab_output",
    "generate_caregap_output",
]
