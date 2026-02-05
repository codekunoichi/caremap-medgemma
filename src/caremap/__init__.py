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
from .radiology_triage import analyze_xray, triage_batch as radiology_triage_batch, TriageResult, format_triage_queue as format_radiology_queue
from .hl7_triage import triage_oru_message, triage_batch as hl7_triage_batch, HL7TriageResult, format_triage_queue as format_hl7_queue, load_sample_messages
from .validators import ValidationError, parse_json_strict
from .prompt_loader import load_prompt, fill_prompt
from .html_translator import translate_fridge_sheet_html, translate_html_file

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
    "analyze_xray",
    "radiology_triage_batch",
    "TriageResult",
    "format_radiology_queue",
    "triage_oru_message",
    "hl7_triage_batch",
    "HL7TriageResult",
    "format_hl7_queue",
    "load_sample_messages",
    "ValidationError",
    "parse_json_strict",
    "load_prompt",
    "fill_prompt",
    "translate_fridge_sheet_html",
    "translate_html_file",
]
