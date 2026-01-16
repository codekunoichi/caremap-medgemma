"""
MedGemma client for CareMap.

Supports both text-only and multimodal (image + text) generation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Union

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Optional multimodal imports (may not be available in all environments)
try:
    from transformers import AutoProcessor, pipeline as hf_pipeline
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


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
        return torch.float16
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
    """
    max_new_tokens: int = 220
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0


class MedGemmaClient:
    """
    Minimal, reliable Hugging Face client for MedGemma.

    Supports two modes:
    - Text-only: Uses AutoModelForCausalLM (default, works everywhere)
    - Multimodal: Uses pipeline("image-text-to-text") for image + text input

    The same model_id (google/medgemma-4b-it) works for both modes.
    """

    def __init__(
        self,
        model_id: str = "google/medgemma-4b-it",
        device: Optional[str] = None,
        gen_cfg: Optional[GenerationConfig] = None,
        enable_multimodal: bool = False,
    ) -> None:
        """
        Initialize the MedGemma client.

        Args:
            model_id: HuggingFace model ID (default: google/medgemma-4b-it)
            device: Preferred device ("cuda", "mps", "cpu", or None for auto)
            gen_cfg: Generation configuration
            enable_multimodal: If True, also load multimodal pipeline for image processing
        """
        self.model_id = model_id
        self.device = pick_device(device)
        self.dtype = pick_dtype(self.device)
        self.gen_cfg = gen_cfg or GenerationConfig()
        self.multimodal_enabled = enable_multimodal and MULTIMODAL_AVAILABLE and PIL_AVAILABLE

        # Text-only model (always loaded)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, use_fast=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=self.dtype,
            device_map=None,  # keep explicit control
        ).to(self.device)
        self.model.eval()

        # Pad token safety: use EOS as pad if not defined.
        if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token_id is not None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        # Multimodal pipeline (optional, loaded only if requested)
        self._multimodal_pipe = None
        if self.multimodal_enabled:
            self._init_multimodal_pipeline()

    def _init_multimodal_pipeline(self) -> None:
        """Initialize the multimodal pipeline for image + text processing."""
        if not MULTIMODAL_AVAILABLE:
            raise RuntimeError("Multimodal support requires transformers with pipeline support")
        if not PIL_AVAILABLE:
            raise RuntimeError("Multimodal support requires PIL (pillow)")

        device_str = "cuda" if self.device.type == "cuda" else "cpu"
        # Note: MPS not fully supported by all pipelines, fall back to CPU
        if self.device.type == "mps":
            device_str = "cpu"

        self._multimodal_pipe = hf_pipeline(
            "image-text-to-text",
            model=self.model_id,
            torch_dtype=self.dtype,
            device=device_str,
        )

    @property
    def supports_multimodal(self) -> bool:
        """Check if multimodal (image) processing is available."""
        return self._multimodal_pipe is not None

    @torch.no_grad()
    def generate(self, prompt: str) -> str:
        """
        Run text generation and return the model's response text.

        Uses the model's chat template for proper formatting with instruction-tuned models.
        """
        # Format prompt using chat template for instruction-tuned models
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(formatted_prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Build generation kwargs based on device and config
        # For MPS (Apple Silicon), force greedy decoding for stability
        if self.device.type == "mps":
            gen_kwargs = dict(
                max_new_tokens=self.gen_cfg.max_new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        else:
            gen_kwargs = dict(
                max_new_tokens=self.gen_cfg.max_new_tokens,
                do_sample=self.gen_cfg.do_sample,
                pad_token_id=self.tokenizer.eos_token_id,
            )
            if self.gen_cfg.do_sample:
                gen_kwargs["temperature"] = self.gen_cfg.temperature
                gen_kwargs["top_p"] = self.gen_cfg.top_p

        outputs = self.model.generate(**inputs, **gen_kwargs)

        # Decode full output (skip_special_tokens removes chat markers)
        text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract model response (after the "model" turn marker)
        # Chat template produces: "user\n{prompt}\nmodel\n{response}"
        if "model" in text.lower():
            parts = text.split("model")
            if len(parts) > 1:
                text = parts[-1].strip()

        return text.strip()

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
                    # URL - let pipeline handle it
                    loaded_images.append(str(img))
                else:
                    raise FileNotFoundError(f"Image not found: {img}")
            else:
                # Assume PIL Image
                loaded_images.append(img)

        # Build messages for the pipeline
        content = []

        # Add images to content
        for img in loaded_images:
            if isinstance(img, str):  # URL
                content.append({"type": "image", "url": img})
            else:  # PIL Image
                content.append({"type": "image", "image": img})

        # Add text prompt
        content.append({"type": "text", "text": prompt})

        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": content})

        # Run pipeline
        output = self._multimodal_pipe(
            text=messages,
            max_new_tokens=self.gen_cfg.max_new_tokens,
        )

        # Extract generated text
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
