# CareMap (MedGemma)

CareMap turns complex health information into **clear, actionable next steps** for patients and caregivers using **MedGemma**, with digital explainers and a printable, PHI‑minimized **one‑page “fridge sheet”** designed for real‑world caregiving.

This project is part of the **MedGemma Impact Challenge (Kaggle Hackathon)** and is intentionally focused on *applied, human‑centered AI* rather than model tuning or benchmarking.

---

## Why CareMap Exists

Modern healthcare systems generate enormous amounts of data, but caregivers are left to manage:
- multiple medications
- overlapping chronic conditions
- missed follow‑ups and screenings
- fragmented instructions across portals and paper

Under stress, memory fails. Phones die. Portals overwhelm.

CareMap is designed for the moment when a caregiver stands in the kitchen, tired, responsible, and unsure what matters *right now*.

---

## What CareMap Does

CareMap takes health data (labs, medications, care gaps, and instructions) and produces:

### 1. A Caregiver‑Friendly Fridge Sheet (Primary Output)
A single printable page that:
- prioritizes **what to do today, this week, and later**
- explains **why medications matter** in plain language
- highlights **pending care gaps with clear next steps**
- provides **who to call** when help is needed
- avoids unnecessary medical or technical detail

### 2. Digital Explainability (Supporting Output)
Clear, high‑level explanations of labs and care actions written at an accessible reading level, designed to reduce confusion rather than increase anxiety.

---

## What CareMap Is *Not*

CareMap is intentionally constrained.

It does **not**:
- diagnose conditions
- recommend treatment changes
- calculate or adjust medication dosages
- replace clinicians or clinical judgment
- function as a full medical record

CareMap favors **silence over speculation** when information is missing or uncertain.

---

## Who This Is For

- Family caregivers managing complex care
- Patients who want clarity without clinical jargon
- Care teams exploring safer patient communication patterns
- Designers and engineers interested in responsible health AI

CareMap is **caregiver‑first**, not clinician‑first.

---

## Why MedGemma

CareMap uses **MedGemma** to:
- translate medical concepts into plain language
- generate high‑level, uncertainty‑aware explanations
- adapt output to caregiver‑appropriate reading levels

MedGemma is used where medical grounding matters and avoided where deterministic rules are safer.

---

## Design Principles

- One page, always
- Action > information
- Plain language over precision
- Cognitive load awareness
- Safety through constraint
- Offline‑friendly by design

---

## Project Status

Current focus:
- Finalizing the one‑page fridge sheet schema
- Defining strict input → output rules
- Establishing golden test cases

Recently added:
- Localization and multilingual support (Bengali, Hindi, Spanish, and more via NLLB-200)

Future work:
- Agentic workflows
- Interactive caregiver tools

---

## Repository Guide

- `INTENT.md` – project purpose and ethical grounding
- `FRIDGE_SHEET_SCHEMA.md` – locked one‑page caregiver schema
- `INPUT_OUTPUT_RULES.md` – deterministic transformation rules
- `SAFETY_AND_LIMITATIONS.md` – explicit non‑goals and safeguards
- `TEST_CASES.md` – golden test cases and quality gates
- `ROADMAP.md` – scoped future directions

---
---

## One‑Time Setup: Hugging Face Access for MedGemma

MedGemma models are **license‑gated** on Hugging Face.  
You must complete the following steps **once** before running CareMap with MedGemma.

### 1) Create / sign in to a Hugging Face account
- Go to: https://huggingface.co
- Sign in (or create an account)

(Optional but recommended)
- Link your GitHub account under **Settings → Linked Accounts**
  - This helps with identity verification for gated models

---

### 2) Generate a Hugging Face access token

1. Visit: https://huggingface.co/settings/tokens  
2. Click **New token**
3. Select **Read** access (this is sufficient)
4. Create the token and **copy it** (you won’t see it again)

---

### 3) Log in from the command line (inside your virtual environment)

With the virtual environment activated:

```bash
huggingface-cli login
```

Paste your access token when prompted.

If `huggingface-cli` is not on your PATH, use:

```bash
python -m huggingface_hub.cli login
```

To verify login:

```bash
python -c "from huggingface_hub import whoami; print(whoami())"
```

---

### 4) Accept the MedGemma model license

While logged in on Hugging Face, visit the MedGemma model page:

- https://huggingface.co/google/medgemma-4b-it

If prompted, click **“Agree and access”** to accept the license.

> Without accepting the license, downloads will fail with a `403` or
> “You are trying to access a gated repo” error.

---

### 5) Run the MedGemma demo

After login and license acceptance:

```bash
python src/hello_world_medgemma.py --mode med --name "Metformin"
```

The first run will download model weights and may take several minutes,
especially on Apple Silicon.

---

### Notes

- MedGemma 4B is a large model; expect high memory usage and slower startup.
- If you encounter memory issues:
  - Close other applications
  - Reduce `--max-new-tokens`
  - Consider CPU execution for testing

This setup is required **once per machine**. Subsequent runs will use the
cached model files.

---


## Quickstart: Install + Run MedGemma Hello World

Follow these steps **in order**.  
Changing the order may cause pip to fail on macOS/Homebrew Python with an
`externally-managed-environment` error.

These steps run the minimal MedGemma demo script located at
`src/hello_world_medgemma.py`.

### 1) Create a virtual environment (one time)

From the root of the repo:

```bash
python3 -m venv .venv
```

### 2) Activate the virtual environment (required)

```bash
source .venv/bin/activate
```

You should now see `(.venv)` in your shell prompt.  
If you **do not** see this, stop — pip installs will fail.

### 3) Upgrade pip *inside* the virtual environment

Once the virtual environment is active:

```bash
python -m pip install --upgrade pip
```

> On macOS, Homebrew-managed Python blocks global pip installs.  
> Upgrading pip is only allowed **inside** a virtual environment.

### 4) Install Python dependencies

```bash
pip install -r requirements.txt
```

> Note: `torch` installation can vary by OS/GPU.  
> If Torch fails to install, install it using the official PyTorch selector
> for your machine, then re-run the command above.

### 5) Run the MedGemma hello world script

Medication explanation:

```bash
python src/hello_world_medgemma.py --mode med --name "Metformin"
```

Lab explanation:

```bash
python src/hello_world_medgemma.py --mode lab --name "Hemoglobin" --flag low
```

### 6) (Optional) Set the MedGemma model id

If you need to use a different MedGemma model id, set it once:

```bash
export MEDGEMMA_MODEL_ID="google/medgemma-2b-it"
```

Or pass it directly:

```bash
python src/hello_world_medgemma.py --model "google/medgemma-2b-it" --mode med --name "Metformin"
```

### Troubleshooting

If you see this error:

```
error: externally-managed-environment
```

It means the virtual environment is **not activated**.  
Activate it with:

```bash
source .venv/bin/activate
```

Then retry the command.

---

## Running the Jupyter Notebook (Local)

This repository includes a Jupyter Notebook intended for interactive exploration and as a Kaggle-style, judge-facing artifact.

Follow these steps to run the notebook locally.

### 1) Activate the virtual environment

From the project root:

```bash
source .venv/bin/activate
```

Verify that Python points to the virtual environment:

```bash
which python
```

You should see a path ending in `.venv/bin/python`.

---

### 2) Register the virtual environment as a Jupyter kernel (one time)

Run this **once** to make the virtual environment selectable inside Jupyter:

```bash
python -m ipykernel install --user \
  --name caremap-medgemma \
  --display-name "CareMap (venv)"
```

---

### 3) Start the Jupyter server

You may use either interface:

**JupyterLab (recommended):**
```bash
jupyter lab
```

**Classic Notebook:**
```bash
jupyter notebook
```

Your browser will open with a file explorer. Open the `.ipynb` notebook from there.

---

### 4) Select the correct kernel inside the notebook

In the notebook UI:
- Click the kernel selector (top-right), or
- Use **Kernel → Change Kernel**

Choose:

**`CareMap (venv)`**

---

### 5) Sanity check (optional but recommended)

Run the following cell to confirm the kernel is correct:

```python
import sys
print(sys.executable)
```

Expected output should point to `.venv/bin/python`.

You can also verify PyTorch and Apple Silicon support:

```python
import torch
print(torch.__version__)
print(torch.backends.mps.is_available())
```

---

### Notes

- Kernel setup is required **only for local use**.
- Kaggle Notebooks manage kernels automatically; you do not need to perform these steps on Kaggle.
- Always ensure the correct kernel is selected to avoid missing-package or model-loading errors.

---

## License

This project is released under the **Apache License 2.0**.

---

CareMap is built with the belief that **clarity is care**.

---