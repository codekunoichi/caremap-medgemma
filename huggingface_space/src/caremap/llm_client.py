"""
MedGemma client for CareMap.

Supports both text-only and multimodal (image + text) generation.
Version-aware: auto-detects MedGemma 1.0 vs 1.5 from model_id and
uses the appropriate HuggingFace API for each.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Union

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# MedGemma 1.5 uses a different model class + processor
try:
    from transformers import AutoModelForImageTextToText, AutoProcessor
    V15_AVAILABLE = True
except ImportError:
    V15_AVAILABLE = False

# Optional multimodal imports (may not be available in all environments)
try:
    from transformers import pipeline as hf_pipeline
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _is_v15(model_id: str) -> bool:
    """Detect MedGemma 1.5 from model_id string."""
    return "1.5" in model_id


def pick_device(prefer: Optional[str] = None) -> torch.device:
    """
    Pick a device with sensible defaults:
      - If prefer is set (e.g., "cuda" or "mps"), use it if available.
      - Else prefer CUDA, then MPS, then CPU.
    """
    prefer = (prefer or "").strip().lower()

    if prefer == "cuda" and torch.cuda.is_available():
        return torch.device("cuda")

    if prefer == "mps" and getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")

    if torch.cuda.is_available():
        return torch.device("cuda")

    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def pick_dtype(device: torch.device) -> torch.dtype:
    """
    Conservative dtype selection for stability.

    Note: MPS (Apple Silicon) needs float32 to avoid NaN issues during generation.
    Only CUDA can safely use float16.
    """
    if device.type == "cuda":
        return torch.bfloat16
    # MPS and CPU need float32 for numerical stability
    return torch.float32


@dataclass
class GenerationConfig:
    """
    Generation defaults intentionally biased toward stability + determinism.

    Note:
      - The 'probability tensor contains inf/nan' error you saw is often triggered by
        sampling on some backends (especially MPS) with certain temperature/top_p values.
      - For v1, default to greedy decoding (do_sample=False).
      - max_new_tokens increased to 1024 to support V3 grounded prompts
        (chain-of-thought reasoning + JSON output).
    """
    max_new_tokens: int = 1024
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0


class MedGemmaClient:
    """
    Minimal, reliable Hugging Face client for MedGemma.

    Version-aware: auto-detects v1 vs v1.5 from model_id.
      - v1  (google/medgemma-4b-it):     AutoModelForCausalLM + AutoTokenizer
      - v1.5 (google/medgemma-1.5-4b-it): AutoModelForImageTextToText + AutoProcessor

    The generate(prompt) interface is identical for both versions.
    """

    def __init__(
        self,
        model_id: str = "google/medgemma-1.5-4b-it",
        device: Optional[str] = None,
        gen_cfg: Optional[GenerationConfig] = None,
        enable_multimodal: bool = False,
    ) -> None:
        """
        Initialize the MedGemma client.

        Args:
            model_id: HuggingFace model ID (auto-detects v1 vs v1.5)
            device: Preferred device ("cuda", "mps", "cpu", or None for auto)
            gen_cfg: Generation configuration
            enable_multimodal: If True, also load multimodal pipeline for image processing
        """
        self.model_id = model_id
        self.device = pick_device(device)
        self.dtype = pick_dtype(self.device)
        self.gen_cfg = gen_cfg or GenerationConfig()
        self.is_v15 = _is_v15(model_id)

        if self.is_v15:
            self._init_v15()
        else:
            self._init_v1()

        # Multimodal pipeline (optional, loaded only if requested)
        self.multimodal_enabled = enable_multimodal and PIPELINE_AVAILABLE and PIL_AVAILABLE
        self._multimodal_pipe = None
        if self.multimodal_enabled:
            self._init_multimodal_pipeline()

    def _init_v1(self) -> None:
        """Load MedGemma v1 with AutoModelForCausalLM + AutoTokenizer."""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, use_fast=True)
        self.processor = None
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=self.dtype,
            device_map=None,
        ).to(self.device)
        self.model.eval()

        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

    def _init_v15(self) -> None:
        """Load MedGemma v1.5 with AutoModelForImageTextToText + AutoProcessor."""
        if not V15_AVAILABLE:
            raise RuntimeError(
                "MedGemma 1.5 requires transformers >= 4.50.0 with "
                "AutoModelForImageTextToText support. "
                "Run: pip install -U transformers"
            )
        self.processor = AutoProcessor.from_pretrained(self.model_id, use_fast=True)
        self.tokenizer = self.processor  # alias so pad_token_id access works
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_id,
            dtype=self.dtype,
            device_map=None,
        ).to(self.device)
        self.model.eval()

    def _init_multimodal_pipeline(self) -> None:
        """Initialize the multimodal pipeline for image + text processing."""
        if not PIPELINE_AVAILABLE:
            raise RuntimeError("Multimodal support requires transformers with pipeline support")
        if not PIL_AVAILABLE:
            raise RuntimeError("Multimodal support requires PIL (pillow)")

        pipe_kwargs = dict(
            task="image-text-to-text",
            model=self.model,
        )
        if self.is_v15:
            pipe_kwargs["processor"] = self.processor
        else:
            pipe_kwargs["tokenizer"] = self.tokenizer

        self._multimodal_pipe = hf_pipeline(**pipe_kwargs)

    @property
    def supports_multimodal(self) -> bool:
        """Check if multimodal (image) processing is available."""
        return self._multimodal_pipe is not None

    @torch.no_grad()
    def generate(self, prompt: str) -> str:
        """
        Run text generation and return the model's response text.

        Uses the model's chat template for proper formatting.
        Works identically for both MedGemma v1 and v1.5.
        """
        if self.is_v15:
            return self._generate_v15(prompt)
        return self._generate_v1(prompt)

    def _generate_v1(self, prompt: str) -> str:
        """Text generation for MedGemma v1 (AutoModelForCausalLM)."""
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        gen_kwargs = self._build_gen_kwargs()
        outputs = self.model.generate(**inputs, **gen_kwargs)

        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract model response (after the "model" turn marker)
        if "model" in text.lower():
            parts = text.split("model")
            if len(parts) > 1:
                text = parts[-1].strip()

        return text.strip()

    def _generate_v15(self, prompt: str) -> str:
        """Text generation for MedGemma v1.5 (AutoModelForImageTextToText)."""
        messages = [
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]

        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.device)

        if "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)

        input_len = inputs["input_ids"].shape[-1]

        gen_kwargs = self._build_gen_kwargs()
        output_ids = self.model.generate(**inputs, **gen_kwargs)
        generated = output_ids[0][input_len:]

        return self.processor.decode(generated, skip_special_tokens=True).strip()

    def _build_gen_kwargs(self) -> dict:
        """Build generation kwargs, forcing greedy decoding on MPS."""
        eos_id = (
            self.processor.tokenizer.eos_token_id
            if self.is_v15 and hasattr(self.processor, "tokenizer")
            else getattr(self.tokenizer, "eos_token_id", None)
        )

        if self.device.type == "mps":
            return dict(
                max_new_tokens=self.gen_cfg.max_new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=eos_id,
            )

        gen_kwargs = dict(
            max_new_tokens=self.gen_cfg.max_new_tokens,
            do_sample=self.gen_cfg.do_sample,
            pad_token_id=eos_id,
        )
        if self.gen_cfg.do_sample:
            gen_kwargs["temperature"] = self.gen_cfg.temperature
            gen_kwargs["top_p"] = self.gen_cfg.top_p

        return gen_kwargs

    def generate_with_images(
        self,
        prompt: str,
        images: List[Union[str, Path, "Image.Image"]],
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        Run multimodal generation with images and text.

        Args:
            prompt: The text prompt/question about the images
            images: List of image paths, URLs, or PIL Image objects
            system_prompt: Optional system prompt for safety constraints

        Returns:
            Generated text response

        Raises:
            RuntimeError: If multimodal mode is not enabled
        """
        if not self.supports_multimodal:
            raise RuntimeError(
                "Multimodal mode not enabled. Initialize client with enable_multimodal=True"
            )

        if not PIL_AVAILABLE:
            raise RuntimeError("PIL (pillow) required for image processing")

        # Load images
        loaded_images = []
        for img in images:
            if isinstance(img, (str, Path)):
                path = Path(img)
                if path.exists():
                    loaded_images.append(Image.open(path))
                elif str(img).startswith(("http://", "https://")):
                    loaded_images.append(str(img))
                else:
                    raise FileNotFoundError(f"Image not found: {img}")
            else:
                loaded_images.append(img)

        # Build messages for the pipeline
        content = []
        for img in loaded_images:
            if isinstance(img, str):
                content.append({"type": "image", "url": img})
            else:
                content.append({"type": "image", "image": img})
        content.append({"type": "text", "text": prompt})

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        output = self._multimodal_pipe(
            text=messages,
            max_new_tokens=self.gen_cfg.max_new_tokens,
        )

        return output[0]["generated_text"][-1]["content"]


# Default system prompt for medical imaging (caregiver-safe)
IMAGING_SYSTEM_PROMPT = """You are a medical assistant helping a family caregiver understand medical images.

Rules:
- Use plain language (6th grade reading level)
- Do NOT diagnose conditions
- Do NOT recommend treatments
- Do NOT provide specific measurements or values
- Always suggest asking the doctor for details
- Keep responses brief and calm
"""
