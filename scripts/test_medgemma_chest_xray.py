#!/usr/bin/env python3
"""
Test MedGemma's multimodal capabilities on chest X-ray.
Demonstrates clinical image interpretation for caregiver-friendly explanation.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from caremap.llm_client import MedGemmaClient


def interpret_chest_xray(image_path: str):
    """Use MedGemma to interpret a chest X-ray for caregivers."""

    print("=" * 60)
    print("MedGemma Chest X-ray Interpretation Demo")
    print("=" * 60)
    print(f"\nImage: {image_path}")

    # Initialize MedGemma with multimodal support
    print("\nLoading MedGemma (multimodal mode)...")
    client = MedGemmaClient(
        model_id="google/medgemma-4b-it",
        enable_multimodal=True
    )
    print(f"Device: {client.device}")

    # Prompt designed for caregiver-friendly output
    prompt = """You are explaining a chest X-ray to a family caregiver of an 82-year-old patient with heart failure.

Look at this chest X-ray and provide:

1. WHAT THE X-RAY SHOWS (2-3 bullet points, simple language):
   - Describe what you see in terms a non-medical person can understand

2. WHAT THIS MEANS FOR DAILY CARE (2-3 bullet points):
   - Connect the findings to practical care actions
   - Explain why certain medications (like water pills) are important

3. WHEN TO CALL THE DOCTOR (2-3 warning signs):
   - Based on these findings, what symptoms should trigger a call?

Use simple words. Avoid medical jargon. Write at a 6th grade reading level."""

    print("\n" + "-" * 60)
    print("Sending to MedGemma...")
    print("-" * 60)

    # Generate interpretation
    response = client.generate_with_images(
        prompt=prompt,
        images=[image_path]
    )

    print("\n" + "=" * 60)
    print("MedGemma Response:")
    print("=" * 60)
    print(response)

    return response


def main():
    # Default image path
    image_path = "data/nih_chest_xray/00000032_001.png"

    if len(sys.argv) > 1:
        image_path = sys.argv[1]

    if not Path(image_path).exists():
        print(f"ERROR: Image not found at {image_path}")
        sys.exit(1)

    interpret_chest_xray(image_path)


if __name__ == "__main__":
    main()
