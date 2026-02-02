#!/usr/bin/env python3
"""
Select specific images for the Radiology Triage Demo.
Filters NIH Chest X-ray dataset for STAT/SOON/ROUTINE buckets.
"""

import pandas as pd
from pathlib import Path


def select_demo_images(csv_path: str = "data/nih_chest_xray/Data_Entry_2017.csv"):
    """Select images for each priority bucket."""

    df = pd.read_csv(csv_path)
    print(f"Total images in dataset: {len(df):,}")

    # STAT: Critical - Cardiomegaly + Edema (+ optionally Effusion)
    # These are acute decompensated heart failure cases
    stat_mask = (
        df['Finding Labels'].str.contains('Cardiomegaly', na=False) &
        df['Finding Labels'].str.contains('Edema', na=False)
    )
    stat_images = df[stat_mask].head(8)

    # SOON: Abnormal - Cardiomegaly + Effusion (no edema) OR Cardiomegaly only
    # These need attention but not emergent
    soon_mask = (
        df['Finding Labels'].str.contains('Cardiomegaly', na=False) &
        df['Finding Labels'].str.contains('Effusion', na=False) &
        ~df['Finding Labels'].str.contains('Edema', na=False)
    )
    soon_images_1 = df[soon_mask].head(5)

    # Also include some Cardiomegaly-only cases
    cardiomegaly_only = df[df['Finding Labels'] == 'Cardiomegaly'].head(5)
    soon_images = pd.concat([soon_images_1, cardiomegaly_only])

    # ROUTINE: No acute findings
    routine_mask = df['Finding Labels'] == 'No Finding'
    routine_images = df[routine_mask].head(15)

    print("\n" + "="*60)
    print("STAT Queue (Critical - Review <1 hour)")
    print("="*60)
    print(f"Count: {len(stat_images)}")
    for idx, row in stat_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    print("\n" + "="*60)
    print("SOON Queue (Abnormal - Review <24 hours)")
    print("="*60)
    print(f"Count: {len(soon_images)}")
    for idx, row in soon_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    print("\n" + "="*60)
    print("ROUTINE Queue (Normal - Review 48-72 hours)")
    print("="*60)
    print(f"Count: {len(routine_images)}")
    for idx, row in routine_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    # Create manifest CSV
    all_images = []

    for _, row in stat_images.iterrows():
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'STAT',
            'findings': row['Finding Labels'],
            'patient_age': row['Patient Age'],
            'patient_gender': row['Patient Gender']
        })

    for _, row in soon_images.iterrows():
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'SOON',
            'findings': row['Finding Labels'],
            'patient_age': row['Patient Age'],
            'patient_gender': row['Patient Gender']
        })

    for _, row in routine_images.iterrows():
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'ROUTINE',
            'findings': row['Finding Labels'],
            'patient_age': row['Patient Age'],
            'patient_gender': row['Patient Gender']
        })

    manifest_df = pd.DataFrame(all_images)
    output_dir = Path("data/nih_chest_xray")
    manifest_path = output_dir / "demo_manifest.csv"
    manifest_df.to_csv(manifest_path, index=False)

    print(f"\n\nManifest saved to: {manifest_path}")
    print(f"Total images to download: {len(manifest_df)}")

    # Generate download commands
    print("\n" + "="*60)
    print("KAGGLE DOWNLOAD COMMANDS")
    print("="*60)

    # Group images by their folder (images_001, images_002, etc.)
    # Image IDs like 00000032_001.png are in images_001 folder
    # We need to figure out which folder each image is in

    image_ids = manifest_df['image_id'].tolist()
    print(f"\nImages to download ({len(image_ids)}):")
    for img_id in image_ids:
        print(f"  - {img_id}")

    return manifest_df


if __name__ == "__main__":
    select_demo_images()
