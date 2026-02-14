#!/usr/bin/env bash
# Build the Kaggle dataset zip for the CareMap competition.
# Expected output: ~10MB (77 files). If it exceeds 15MB, something is wrong.
#
# Usage: ./build_kaggle_dataset.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

OUT_DIR="kaggle_dataset"
ZIP_NAME="caremap-medgemma-dataset.zip"
ZIP_PATH="$OUT_DIR/$ZIP_NAME"
MAX_SIZE_MB=15

mkdir -p "$OUT_DIR"
rm -f "$ZIP_PATH"

echo "Building $ZIP_PATH ..."

zip -r "$ZIP_PATH" \
  src/caremap/__init__.py \
  src/caremap/assemble_fridge_sheet.py \
  src/caremap/caregap_interpretation.py \
  src/caremap/fridge_sheet_html.py \
  src/caremap/hl7_triage.py \
  src/caremap/html_translator.py \
  src/caremap/imaging_interpretation.py \
  src/caremap/lab_interpretation.py \
  src/caremap/llm_client.py \
  src/caremap/medication_interpretation.py \
  src/caremap/multilingual_fridge_sheet.py \
  src/caremap/priority_rules.py \
  src/caremap/prompt_loader.py \
  src/caremap/radiology_triage.py \
  src/caremap/reading_level.py \
  src/caremap/safety_validator.py \
  src/caremap/translation.py \
  src/caremap/validators.py \
  prompts/ \
  examples/ \
  data/nih_chest_xray/demo_images/ \
  data/nih_chest_xray/radiology_priority_rules.csv \
  data/nih_chest_xray/sample_manifest.csv \
  requirements.txt

# Size guard
SIZE_BYTES=$(stat -f%z "$ZIP_PATH" 2>/dev/null || stat -c%s "$ZIP_PATH" 2>/dev/null)
SIZE_MB=$(( SIZE_BYTES / 1048576 ))

echo ""
echo "Created: $ZIP_PATH"
echo "Size:    ${SIZE_MB}MB (${SIZE_BYTES} bytes)"

if [ "$SIZE_MB" -gt "$MAX_SIZE_MB" ]; then
  echo "ERROR: Zip is ${SIZE_MB}MB — exceeds ${MAX_SIZE_MB}MB limit!"
  echo "Check for accidentally included large files (full NIH dataset, model weights, etc)."
  exit 1
fi

FILE_COUNT=$(unzip -l "$ZIP_PATH" | tail -1 | awk '{print $2}')
echo "Files:   $FILE_COUNT"
echo "Done."
