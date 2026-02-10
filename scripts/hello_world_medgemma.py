

"""
CareMap – MedGemma Hello World (Text-only)

Purpose:
- Demonstrate a minimal, study-friendly interaction with MedGemma:
  1) load tokenizer + model
  2) send a constrained caregiver-facing prompt
  3) print the generated output

Notes:
- This is intentionally NOT integrated into the CareMap pipeline yet.
- Start here to understand model invocation and prompt behavior.
- Keep temperature low for stability in healthcare contexts.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


# ---- Configuration ----

# Prefer an instruction-tuned MedGemma model for text generation.
# If you don't have access to this exact ID, replace it with the MedGemma
# model you have permission to use (e.g., another `google/medgemma-*` variant).
DEFAULT_MODEL_ID = "google/medgemma-4b-it"

# Keep generation conservative.
DEFAULT_MAX_NEW_TOKENS = 180
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.9


def pick_device() -> str:
    """Pick a reasonable device (CUDA > MPS > CPU)."""
    if torch.cuda.is_available():
        return "cuda"
    # Apple Silicon (Metal Performance Shaders)
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def build_prompt_medication(medication_name: str) -> str:
    """Minimal caregiver-friendly prompt for medication purpose."""
    return f"""
You are a medical assistant helping a caregiver.

Task:
Explain in plain language what this medication is for.

Medication: {medication_name}

Rules:
- Do not diagnose conditions
- Do not provide medical advice
- Do not suggest dosage changes
- Do not recommend starting/stopping medications
- Use simple, calm language (about a 6th grade reading level)
- Keep it to 3-5 short sentences
""".strip()


def build_prompt_lab(test_name: str, qualitative_flag: str) -> str:
    """Minimal caregiver-friendly prompt for high-level lab explanation."""
    return f"""
You are a medical assistant helping a caregiver.

Task:
Explain this lab test result in plain language.

Test: {test_name}
Result: {qualitative_flag}

Rules:
- Do not diagnose conditions
- Do not provide medical advice
- Do not suggest treatment changes
- Do not include numeric reference ranges or thresholds
- Use simple, calm language (about a 6th grade reading level)
- Provide ONE question the caregiver can ask the doctor
- Keep it to 4-6 short sentences total
""".strip()


def load_model(model_id: str, device: str) -> tuple[AutoTokenizer, AutoModelForCausalLM]:
    """Load tokenizer and model with a helpful error if the repo is missing/gated."""
    print(f"[CareMap] Loading model: {model_id}")

    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
    except Exception as e:
        raise SystemExit(
            "\n[CareMap] Failed to load tokenizer.\n"
            f"Model id: {model_id}\n\n"
            "Common causes:\n"
            "  1) The model id is incorrect (not found on Hugging Face).\n"
            "  2) The model is gated and you need to accept the license on the model page.\n"
            "  3) You need to authenticate with a Hugging Face token.\n\n"
            "Fix:\n"
            "  - Verify the model id exists (example: google/medgemma-4b-it).\n"
            "  - If gated, click 'Agree and access' on the model page while logged in.\n"
            "  - Then run:  huggingface-cli login\n"
            "  - Or set an env var token:  export HF_TOKEN=...  (or use the HF_HOME cache)\n\n"
            f"Original error: {e}\n"
        ) from e

    # Use fp16 on CUDA for speed/memory; use fp32 on MPS/CPU for numerical stability.
    # (MPS + fp16 can sometimes produce NaNs during sampling.)
    dtype = torch.float16 if device == "cuda" else torch.float32

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
        )
    except Exception as e:
        raise SystemExit(
            "\n[CareMap] Failed to load model weights.\n"
            f"Model id: {model_id}\n\n"
            "Common causes:\n"
            "  1) Gated model: you must accept the license on Hugging Face.\n"
            "  2) Not authenticated: run `huggingface-cli login`.\n"
            "  3) Your machine doesn't have enough RAM/VRAM for this model.\n\n"
            "Tips:\n"
            "  - On Apple Silicon, you may need to close other apps.\n"
            "  - Try a smaller model if available.\n"
            "  - Use `--max-new-tokens 80` for a quicker first run.\n\n"
            f"Original error: {e}\n"
        ) from e

    # If running on CPU/MPS, move model explicitly.
    if device != "cuda":
        model.to(device)

    model.eval()
    return tokenizer, model


@torch.no_grad()
def generate(
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    prompt: str,
    device: str,
    max_new_tokens: int,
    temperature: float,
    top_p: float,
) -> str:
    """Generate a completion for the given prompt."""
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Numerical stability hint (mostly relevant for sampling on some backends)
    if device == "mps":
        torch.set_float32_matmul_precision("high")

    # For maximum stability on Apple Silicon (MPS), force greedy decoding and
    # do NOT pass sampling-related parameters (temperature/top_p).
    if device == "mps":
        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            do_sample=False,
            num_beams=1,
            pad_token_id=tokenizer.eos_token_id,
        )
    else:
        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    outputs = model.generate(**inputs, **gen_kwargs)

    text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Heuristic: return only the portion after the prompt if the model echoes it.
    if text.startswith(prompt):
        text = text[len(prompt) :].strip()

    return text.strip()


def parse_args(argv: list[str]) -> dict:
    """
    Very small argument parser to avoid adding additional dependencies.
    Usage examples:
      python src/hello_world_medgemma.py --mode med --name Metformin
      python src/hello_world_medgemma.py --mode lab --name Hemoglobin --flag low
    """
    args = {
        "model_id": os.getenv("MEDGEMMA_MODEL_ID", DEFAULT_MODEL_ID),
        "mode": "med",  # med | lab
        "name": "Metformin",
        "flag": "high",
        "max_new_tokens": DEFAULT_MAX_NEW_TOKENS,
        "temperature": DEFAULT_TEMPERATURE,
        "top_p": DEFAULT_TOP_P,
    }

    it = iter(argv)
    for token in it:
        if token == "--model":
            args["model_id"] = next(it)
        elif token == "--mode":
            args["mode"] = next(it)
        elif token == "--name":
            args["name"] = next(it)
        elif token == "--flag":
            args["flag"] = next(it)
        elif token == "--max-new-tokens":
            args["max_new_tokens"] = int(next(it))
        elif token == "--temperature":
            args["temperature"] = float(next(it))
        elif token == "--top-p":
            args["top_p"] = float(next(it))
        elif token in ("-h", "--help"):
            print(
                "CareMap – MedGemma Hello World\n"
                "Usage:\n"
                "  python src/hello_world_medgemma.py --mode med --name Metformin\n"
                "  python src/hello_world_medgemma.py --mode lab --name Hemoglobin --flag low\n"
                "Options:\n"
                "  --model <id>            Hugging Face model id (or set MEDGEMMA_MODEL_ID)\n"
                "  --mode <med|lab>        Prompt type\n"
                "  --name <string>         Medication name OR lab test name\n"
                "  --flag <high|low|normal|unknown>  (lab mode only)\n"
                "  --max-new-tokens <int>\n"
                "  --temperature <float>\n"
                "  --top-p <float>\n"
            )
            sys.exit(0)
        else:
            raise SystemExit(f"Unknown argument: {token}. Try --help.")

    return args


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    args = parse_args(argv)

    device = pick_device()
    print(f"[CareMap] Device: {device}")

    tokenizer, model = load_model(args["model_id"], device)

    if args["mode"] == "med":
        prompt = build_prompt_medication(args["name"])
        title = f"Medication explanation: {args['name']}"
    elif args["mode"] == "lab":
        prompt = build_prompt_lab(args["name"], args["flag"])
        title = f"Lab explanation: {args['name']} ({args['flag']})"
    else:
        raise SystemExit("Invalid --mode. Use 'med' or 'lab'.")

    print("\n" + "=" * 72)
    print(f"{title}")
    print("=" * 72)
    print("\n[Prompt]\n" + prompt)

    response = generate(
        tokenizer=tokenizer,
        model=model,
        prompt=prompt,
        device=device,
        max_new_tokens=args["max_new_tokens"],
        temperature=args["temperature"],
        top_p=args["top_p"],
    )

    print("\n[Model output]\n" + response)
    print("=" * 72 + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())