"""
CareMap - Caregiver Fridge Sheet Generator using MedGemma

This module provides tools for generating caregiver-friendly one-page
summaries from EHR data using MedGemma for plain-language explanations.
"""

from .llm_client import MedGemmaClient, GenerationConfig
from .assemble_fridge_sheet import build_fridge_sheet, BuildLimits
from .medication_interpretation import interpret_medication
from .lab_interpretation import interpret_lab
from .caregap_interpretation import interpret_caregap
from .imaging_interpretation import interpret_imaging_report, interpret_imaging_with_image
from .validators import ValidationError, parse_json_strict
from .prompt_loader import load_prompt, fill_prompt

__all__ = [
    "MedGemmaClient",
    "GenerationConfig",
    "build_fridge_sheet",
    "BuildLimits",
    "interpret_medication",
    "interpret_lab",
    "interpret_caregap",
    "interpret_imaging_report",
    "interpret_imaging_with_image",
    "ValidationError",
    "parse_json_strict",
    "load_prompt",
    "fill_prompt",
]
