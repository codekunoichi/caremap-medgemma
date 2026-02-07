"""
Quick smoke test: MedGemma 1.5 4B on Mac (MPS/CPU).

Loads the new model, fills in the medication_prompt_v1 template with
a sample medication, and prints the JSON response.

Usage:
    source .venv/bin/activate
    PYTHONPATH=src python test_medgemma15.py
"""

import time
import torch
from pathlib import Path
from transformers import AutoProcessor, AutoModelForImageTextToText


# ---------------------------------------------------------------------------
# 1. Device + dtype selection (Mac-safe)
# ---------------------------------------------------------------------------
if torch.cuda.is_available():
    device = torch.device("cuda")
    dtype = torch.bfloat16
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    device = torch.device("mps")
    # MPS: bfloat16 may not be supported; fall back to float32
    dtype = torch.float32
else:
    device = torch.device("cpu")
    dtype = torch.float32

print(f"Device : {device}")
print(f"Dtype  : {dtype}")

# ---------------------------------------------------------------------------
# 2. Load MedGemma 1.5
# ---------------------------------------------------------------------------
MODEL_ID = "google/medgemma-1.5-4b-it"

print(f"\nLoading {MODEL_ID} ...")
t0 = time.time()

processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForImageTextToText.from_pretrained(
    MODEL_ID,
    torch_dtype=dtype,
    device_map=None,
).to(device)
model.eval()

print(f"Model loaded in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# 3. Build a medication prompt from v1 template
# ---------------------------------------------------------------------------
template_path = Path("prompts/medication_prompt_v1.txt")
template = template_path.read_text()

# Sample medication (Metformin — common, well-known)
prompt = template.replace("{{MEDICATION_NAME}}", "Metformin 500mg") \
                 .replace("{{WHEN_TO_GIVE}}", "Take 1 tablet by mouth twice daily with meals") \
                 .replace("{{CLINICIAN_NOTES}}", "Monitor blood sugar regularly") \
                 .replace("{{INTERACTION_NOTES}}", "")

# ---------------------------------------------------------------------------
# 4. Generate — using the new processor.apply_chat_template API
# ---------------------------------------------------------------------------
messages = [
    {"role": "user", "content": [{"type": "text", "text": prompt}]}
]

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
).to(device)

# Cast pixel values if present (text-only won't have them)
if "pixel_values" in inputs:
    inputs["pixel_values"] = inputs["pixel_values"].to(dtype)

input_len = inputs["input_ids"].shape[-1]
print(f"\nPrompt tokens: {input_len}")
print("Generating ...")

t0 = time.time()
with torch.inference_mode():
    output_ids = model.generate(
        **inputs,
        max_new_tokens=512,
        do_sample=False,
    )
    generated = output_ids[0][input_len:]

response = processor.decode(generated, skip_special_tokens=True)
elapsed = time.time() - t0

# ---------------------------------------------------------------------------
# 5. Print results
# ---------------------------------------------------------------------------
print(f"Generation time: {elapsed:.1f}s")
print(f"Output tokens  : {len(generated)}")
print(f"\n{'='*60}")
print("MedGemma 1.5 Response:")
print('='*60)
print(response)
print('='*60)

# Quick JSON validity check (strip markdown fences if present)
import json
import re
clean = re.sub(r"^```(?:json)?\s*", "", response.strip())
clean = re.sub(r"\s*```$", "", clean.strip())
try:
    parsed = json.loads(clean)
    print("\nJSON valid! Keys:", list(parsed.keys()))
    expected = {"medication", "why_it_matters", "when_to_give", "important_note"}
    if set(parsed.keys()) == expected:
        print("All expected keys present.")
    else:
        missing = expected - set(parsed.keys())
        extra = set(parsed.keys()) - expected
        if missing:
            print(f"Missing keys: {missing}")
        if extra:
            print(f"Extra keys: {extra}")
except json.JSONDecodeError as e:
    print(f"\nJSON parse failed: {e}")
    print("(This is expected if the model wraps output in markdown fences)")
