"""
CareMap Structured Output Package.

This package provides an alternative approach to generating caregiver-friendly
outputs using Pydantic schemas and the `outlines` library for guaranteed
valid JSON generation.

Comparison with caremap package:
- caremap: Uses prompt engineering + post-hoc JSON parsing
- caremap_structured: Uses outlines for token-level JSON constraints

Both approaches share the same safety philosophy:
- No diagnosis language
- No treatment recommendations
- Plain language (6th grade reading level)
- Always defer to clinician
"""
from .schemas import (
    MedicationOutputV1,
    MedicationOutputV2,
    ImagingOutputV1,
    ImagingOutputV2,
    LabOutputV1,
    LabOutputV2,
    CareGapOutputV1,
    CareGapOutputV2,
)

__all__ = [
    "MedicationOutputV1",
    "MedicationOutputV2",
    "ImagingOutputV1",
    "ImagingOutputV2",
    "LabOutputV1",
    "LabOutputV2",
    "CareGapOutputV1",
    "CareGapOutputV2",
]
