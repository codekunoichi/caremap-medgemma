"""
Structured output generator using outlines library.

This module provides MedGemma generation with guaranteed valid JSON output
by constraining token generation at the logit level.

Key difference from caremap approach:
- caremap: Generate free text -> Parse JSON -> Validate
- caremap_structured: Constrain generation -> Always valid JSON

Requires: pip install outlines
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Type, TypeVar, Union

import torch

# Outlines imports (will fail gracefully if not installed)
try:
    import outlines
    from outlines import models, generate
    OUTLINES_AVAILABLE = True
except ImportError:
    OUTLINES_AVAILABLE = False

from pydantic import BaseModel

from ..schemas.medication import MedicationOutputV1, MedicationOutputV2
from ..schemas.imaging import ImagingOutputV1, ImagingOutputV2
from ..schemas.lab import LabOutputV1, LabOutputV2
from ..schemas.caregap import CareGapOutputV1, CareGapOutputV2


T = TypeVar("T", bound=BaseModel)


def pick_device(prefer: Optional[str] = None) -> str:
    """Pick best available device as string for outlines."""
    prefer = (prefer or "").strip().lower()

    if prefer == "cuda" and torch.cuda.is_available():
        return "cuda"

    if prefer == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"

    if torch.cuda.is_available():
        return "cuda"

    # Note: outlines may have limited MPS support
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"

    return "cpu"


@dataclass
class StructuredGenerationConfig:
    """Configuration for structured generation."""

    max_tokens: int = 512
    temperature: float = 0.0  # Deterministic for reproducibility


class StructuredMedGemmaClient:
    """
    MedGemma client with structured output generation via outlines.

    Unlike the free-form MedGemmaClient in caremap, this client guarantees
    valid JSON output by constraining token generation to match Pydantic schemas.

    Example:
        client = StructuredMedGemmaClient()
        result = client.generate(MedicationOutputV2, prompt)
        # result is guaranteed to be a valid MedicationOutputV2 instance
    """

    def __init__(
        self,
        model_id: str = "google/medgemma-4b-it",
        device: Optional[str] = None,
        config: Optional[StructuredGenerationConfig] = None,
    ) -> None:
        if not OUTLINES_AVAILABLE:
            raise RuntimeError(
                "outlines library not installed. Install with: pip install outlines"
            )

        self.model_id = model_id
        self.device = pick_device(device)
        self.config = config or StructuredGenerationConfig()

        # Load model through outlines
        # Note: outlines.models.transformers handles device placement
        print(f"Loading {model_id} via outlines on {self.device}...")
        self.model = models.transformers(
            model_id,
            device=self.device,
        )

        # Cache for generators (one per schema type)
        self._generators: dict = {}

    def _get_generator(self, schema: Type[T]):
        """Get or create a generator for the given schema."""
        schema_name = schema.__name__

        if schema_name not in self._generators:
            print(f"Creating generator for {schema_name}...")
            self._generators[schema_name] = generate.json(self.model, schema)

        return self._generators[schema_name]

    def generate(self, schema: Type[T], prompt: str) -> T:
        """
        Generate structured output matching the given Pydantic schema.

        Args:
            schema: Pydantic model class defining the output structure
            prompt: The prompt to send to MedGemma

        Returns:
            Instance of the schema class with generated content

        Raises:
            RuntimeError: If outlines is not installed
        """
        generator = self._get_generator(schema)
        result = generator(prompt)
        return result


# =============================================================================
# Convenience functions matching caremap interface
# =============================================================================


def _load_prompt_template(prompt_file: str) -> str:
    """Load a prompt template from the prompts directory."""
    # Look for prompts in the caremap package
    prompts_dir = Path(__file__).parent.parent.parent / "caremap" / "prompts"
    if not prompts_dir.exists():
        # Try project root
        prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"

    prompt_path = prompts_dir / prompt_file
    if prompt_path.exists():
        return prompt_path.read_text()

    raise FileNotFoundError(f"Prompt template not found: {prompt_file}")


def _fill_prompt(template: str, variables: dict) -> str:
    """Fill in template variables."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def generate_medication_output(
    client: StructuredMedGemmaClient,
    medication_name: str,
    sig_text: str,
    clinician_notes: str = "",
    interaction_notes: str = "",
    version: str = "v2",
) -> Union[MedicationOutputV1, MedicationOutputV2]:
    """
    Generate structured medication interpretation.

    Args:
        client: StructuredMedGemmaClient instance
        medication_name: Name of the medication
        sig_text: Prescription instructions
        clinician_notes: Additional notes from clinician
        interaction_notes: Drug interaction warnings
        version: "v1" for constrained output, "v2" for richer output

    Returns:
        MedicationOutputV1 or MedicationOutputV2 instance (guaranteed valid)
    """
    # Select schema and prompt based on version
    if version == "v1":
        schema = MedicationOutputV1
        prompt_file = "medication_prompt_v1.txt"
    else:
        schema = MedicationOutputV2
        prompt_file = "medication_prompt_v3_grounded.txt"  # Use V3 grounded prompt

    template = _load_prompt_template(prompt_file)
    prompt = _fill_prompt(
        template,
        {
            "MEDICATION_NAME": medication_name,
            "SIG_TEXT": sig_text,
            "CLINICIAN_NOTES": clinician_notes,
            "INTERACTION_NOTES": interaction_notes,
        },
    )

    return client.generate(schema, prompt)


def generate_imaging_output(
    client: StructuredMedGemmaClient,
    study_type: str,
    report_text: str,
    flag: str = "normal",
    version: str = "v2",
) -> Union[ImagingOutputV1, ImagingOutputV2]:
    """
    Generate structured imaging interpretation.

    Args:
        client: StructuredMedGemmaClient instance
        study_type: Type of imaging study
        report_text: Radiology report text
        flag: Status flag (normal, needs_follow_up, urgent)
        version: "v1" for constrained output, "v2" for richer output

    Returns:
        ImagingOutputV1 or ImagingOutputV2 instance (guaranteed valid)
    """
    if version == "v1":
        schema = ImagingOutputV1
        prompt_file = "imaging_prompt_v1.txt"
    else:
        schema = ImagingOutputV2
        prompt_file = "imaging_prompt_v3_grounded.txt"

    template = _load_prompt_template(prompt_file)
    prompt = _fill_prompt(
        template,
        {
            "STUDY_TYPE": study_type,
            "REPORT_TEXT": report_text,
            "FLAG": flag,
        },
    )

    return client.generate(schema, prompt)


def generate_lab_output(
    client: StructuredMedGemmaClient,
    test_name: str,
    meaning_category: str,
    source_note: str = "",
    version: str = "v2",
) -> Union[LabOutputV1, LabOutputV2]:
    """
    Generate structured lab interpretation.

    Args:
        client: StructuredMedGemmaClient instance
        test_name: Name of the lab test
        meaning_category: Pre-computed category (Normal, Slightly off, Needs follow-up)
        source_note: Optional non-numeric context
        version: "v1" for constrained output, "v2" for richer output

    Returns:
        LabOutputV1 or LabOutputV2 instance (guaranteed valid)
    """
    if version == "v1":
        schema = LabOutputV1
        prompt_file = "lab_prompt_v1.txt"
    else:
        schema = LabOutputV2
        prompt_file = "lab_prompt_v2_experimental.txt"

    template = _load_prompt_template(prompt_file)
    prompt = _fill_prompt(
        template,
        {
            "TEST_NAME": test_name,
            "MEANING_CATEGORY": meaning_category,
            "SOURCE_NOTE": source_note,
        },
    )

    return client.generate(schema, prompt)


def generate_caregap_output(
    client: StructuredMedGemmaClient,
    item_text: str,
    next_step: str,
    time_bucket: str,
    source: str = "",
    version: str = "v2",
) -> Union[CareGapOutputV1, CareGapOutputV2]:
    """
    Generate structured care gap interpretation.

    Args:
        client: StructuredMedGemmaClient instance
        item_text: Description of the care gap
        next_step: Concrete instruction from source
        time_bucket: Urgency category (Today, This Week, Later)
        source: Optional source of the care gap
        version: "v1" for constrained output, "v2" for richer output

    Returns:
        CareGapOutputV1 or CareGapOutputV2 instance (guaranteed valid)
    """
    if version == "v1":
        schema = CareGapOutputV1
        prompt_file = "caregap_prompt_v1.txt"
    else:
        schema = CareGapOutputV2
        prompt_file = "caregap_prompt_v2_experimental.txt"

    template = _load_prompt_template(prompt_file)
    prompt = _fill_prompt(
        template,
        {
            "ITEM_TEXT": item_text,
            "NEXT_STEP": next_step,
            "TIME_BUCKET": time_bucket,
            "SOURCE": source,
        },
    )

    return client.generate(schema, prompt)
