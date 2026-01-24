"""
Pydantic schemas for CareMap structured outputs.

These schemas define the exact JSON structure that MedGemma must produce.
When used with outlines, the model is constrained at the token level
to only generate valid JSON matching these schemas.
"""
from .medication import MedicationOutputV1, MedicationOutputV2
from .imaging import ImagingOutputV1, ImagingOutputV2
from .lab import LabOutputV1, LabOutputV2
from .caregap import CareGapOutputV1, CareGapOutputV2

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
