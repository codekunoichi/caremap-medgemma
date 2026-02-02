#!/usr/bin/env python3
"""
Select demo images from the downloaded NIH sample dataset.
"""

import pandas as pd
from pathlib import Path

def select_from_sample():
    """Find images for each priority bucket from available sample."""

    # Load sample labels
    labels_path = Path("data/nih_chest_xray/download/sample_labels.csv")
    df = pd.read_csv(labels_path)

    # Check which images actually exist
    images_dir = Path("data/nih_chest_xray/download/sample/images")
    available = set(f.name for f in images_dir.glob("*.png"))
    df = df[df['Image Index'].isin(available)]

    print(f"Available images in sample: {len(df):,}")

    # STAT: Critical - Cardiomegaly + Edema (acute heart failure)
    stat_mask = (
        df['Finding Labels'].str.contains('Cardiomegaly', na=False) &
        df['Finding Labels'].str.contains('Edema', na=False)
    )
    stat_images = df[stat_mask].head(3)

    # If not enough STAT, also include Cardiomegaly + Effusion + something else serious
    if len(stat_images) < 3:
        alt_stat_mask = (
            df['Finding Labels'].str.contains('Cardiomegaly', na=False) &
            df['Finding Labels'].str.contains('Effusion', na=False) &
            (df['Finding Labels'].str.contains('Infiltration', na=False) |
             df['Finding Labels'].str.contains('Pneumonia', na=False))
        )
        alt_stat = df[alt_stat_mask & ~stat_mask].head(3 - len(stat_images))
        stat_images = pd.concat([stat_images, alt_stat])

    # SOON: Abnormal - Cardiomegaly alone or with mild findings
    soon_mask = (
        df['Finding Labels'].str.contains('Cardiomegaly', na=False) &
        ~df['Finding Labels'].str.contains('Edema', na=False)
    )
    soon_images = df[soon_mask].head(8)

    # ROUTINE: No acute findings
    routine_mask = df['Finding Labels'] == 'No Finding'
    routine_images = df[routine_mask].head(15)

    print("\n" + "="*60)
    print("STAT Queue (Critical)")
    print("="*60)
    print(f"Count: {len(stat_images)}")
    for _, row in stat_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    print("\n" + "="*60)
    print("SOON Queue (Abnormal)")
    print("="*60)
    print(f"Count: {len(soon_images)}")
    for _, row in soon_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    print("\n" + "="*60)
    print("ROUTINE Queue (Normal)")
    print("="*60)
    print(f"Count: {len(routine_images)}")
    for _, row in routine_images.iterrows():
        print(f"  {row['Image Index']}: {row['Finding Labels']}")

    # Create manifest
    all_images = []

    for _, row in stat_images.iterrows():
        age_str = row['Patient Age']
        age = int(age_str.replace('Y', '')) if isinstance(age_str, str) else age_str
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'STAT',
            'findings': row['Finding Labels'],
            'patient_age': age,
            'patient_gender': row['Patient Gender']
        })

    for _, row in soon_images.iterrows():
        age_str = row['Patient Age']
        age = int(age_str.replace('Y', '')) if isinstance(age_str, str) else age_str
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'SOON',
            'findings': row['Finding Labels'],
            'patient_age': age,
            'patient_gender': row['Patient Gender']
        })

    for _, row in routine_images.iterrows():
        age_str = row['Patient Age']
        age = int(age_str.replace('Y', '')) if isinstance(age_str, str) else age_str
        all_images.append({
            'image_id': row['Image Index'],
            'priority': 'ROUTINE',
            'findings': row['Finding Labels'],
            'patient_age': age,
            'patient_gender': row['Patient Gender']
        })

    manifest_df = pd.DataFrame(all_images)
    output_path = Path("data/nih_chest_xray/sample_manifest.csv")
    manifest_df.to_csv(output_path, index=False)

    print(f"\n\nManifest saved to: {output_path}")
    print(f"Total images: {len(manifest_df)}")
    print(f"  STAT: {len(stat_images)}")
    print(f"  SOON: {len(soon_images)}")
    print(f"  ROUTINE: {len(routine_images)}")

    return manifest_df

if __name__ == "__main__":
    select_from_sample()
