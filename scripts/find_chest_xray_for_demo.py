#!/usr/bin/env python3
"""
Find ideal NIH Chest X-ray images for CareMap demo.
Looks for images showing Cardiomegaly (enlarged heart) - perfect for Dadu's heart failure story.
"""

import pandas as pd
from pathlib import Path


def find_demo_images(csv_path: str = "data/nih_chest_xray/Data_Entry_2017.csv"):
    """Find chest X-rays with findings relevant to heart failure patient."""

    df = pd.read_csv(csv_path)

    print(f"Total images in dataset: {len(df):,}")
    print(f"\nColumns: {list(df.columns)}")

    # The 'Finding Labels' column contains pipe-separated labels
    # e.g., "Cardiomegaly|Effusion" or "No Finding"

    print("\n" + "="*60)
    print("FINDINGS RELEVANT TO DADU (Heart Failure Patient)")
    print("="*60)

    # 1. Cardiomegaly only (cleanest example)
    cardiomegaly_only = df[df['Finding Labels'] == 'Cardiomegaly']
    print(f"\n1. Cardiomegaly ONLY: {len(cardiomegaly_only):,} images")
    if len(cardiomegaly_only) > 0:
        print("   Sample image IDs:")
        for img in cardiomegaly_only['Image Index'].head(5):
            print(f"   - {img}")

    # 2. Cardiomegaly + Effusion (heart failure with fluid)
    cardio_effusion = df[df['Finding Labels'].str.contains('Cardiomegaly') &
                         df['Finding Labels'].str.contains('Effusion')]
    print(f"\n2. Cardiomegaly + Effusion: {len(cardio_effusion):,} images")
    if len(cardio_effusion) > 0:
        print("   Sample image IDs:")
        for idx, row in cardio_effusion.head(5).iterrows():
            print(f"   - {row['Image Index']} ({row['Finding Labels']})")

    # 3. Cardiomegaly + Edema (acute heart failure)
    cardio_edema = df[df['Finding Labels'].str.contains('Cardiomegaly') &
                      df['Finding Labels'].str.contains('Edema')]
    print(f"\n3. Cardiomegaly + Edema: {len(cardio_edema):,} images")
    if len(cardio_edema) > 0:
        print("   Sample image IDs:")
        for idx, row in cardio_edema.head(5).iterrows():
            print(f"   - {row['Image Index']} ({row['Finding Labels']})")

    # 4. All images with Cardiomegaly
    all_cardiomegaly = df[df['Finding Labels'].str.contains('Cardiomegaly')]
    print(f"\n4. ANY image with Cardiomegaly: {len(all_cardiomegaly):,} images")

    # Recommend best options
    print("\n" + "="*60)
    print("RECOMMENDATIONS FOR DEMO")
    print("="*60)

    print("""
For MedGemma demo, pick ONE image showing:

OPTION A - Simple (Cardiomegaly only):
  - Clear enlarged heart
  - Easy for MedGemma to explain
  - Good for: "This X-ray shows an enlarged heart..."

OPTION B - Complex (Cardiomegaly + Effusion):
  - Shows heart failure complications
  - MedGemma can explain multiple findings
  - Good for: "This shows enlarged heart AND fluid buildup..."

OPTION C - Acute (Cardiomegaly + Edema):
  - Shows decompensated heart failure
  - Explains why Furosemide (water pill) is critical
  - Good for: "This shows fluid in the lungs from heart failure..."
""")

    # Save filtered lists for easy reference
    output_dir = Path("data/nih_chest_xray")
    output_dir.mkdir(parents=True, exist_ok=True)

    if len(cardiomegaly_only) > 0:
        cardiomegaly_only.head(20).to_csv(output_dir / "cardiomegaly_only_samples.csv", index=False)
        print(f"\nSaved: {output_dir}/cardiomegaly_only_samples.csv")

    if len(cardio_effusion) > 0:
        cardio_effusion.head(20).to_csv(output_dir / "cardiomegaly_effusion_samples.csv", index=False)
        print(f"Saved: {output_dir}/cardiomegaly_effusion_samples.csv")

    return {
        'cardiomegaly_only': cardiomegaly_only,
        'cardio_effusion': cardio_effusion,
        'cardio_edema': cardio_edema,
        'all_cardiomegaly': all_cardiomegaly
    }


if __name__ == "__main__":
    import sys

    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/nih_chest_xray/Data_Entry_2017.csv"

    if not Path(csv_path).exists():
        print(f"ERROR: CSV not found at {csv_path}")
        print("\nPlease download Data_Entry_2017.csv from:")
        print("https://www.kaggle.com/datasets/nih-chest-xrays/data")
        print(f"\nThen save it to: {csv_path}")
        sys.exit(1)

    find_demo_images(csv_path)
