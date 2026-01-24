"""
Comparison Demo: caremap vs caremap_structured approaches.

This demo runs the same inputs through both approaches and compares:
1. Output quality and completeness
2. JSON validity (failures vs guaranteed)
3. Schema adherence
4. Performance characteristics

Run with:
    PYTHONPATH=src .venv/bin/python -m caremap_structured.comparison_demo
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

# Check if outlines is available
try:
    import outlines
    OUTLINES_AVAILABLE = True
except ImportError:
    OUTLINES_AVAILABLE = False


@dataclass
class ComparisonResult:
    """Result of comparing both approaches on a single input."""

    input_data: Dict[str, Any]
    caremap_output: Optional[Dict[str, Any]]
    caremap_error: Optional[str]
    caremap_time_ms: float
    structured_output: Optional[Dict[str, Any]]
    structured_error: Optional[str]
    structured_time_ms: float

    @property
    def caremap_succeeded(self) -> bool:
        return self.caremap_error is None

    @property
    def structured_succeeded(self) -> bool:
        return self.structured_error is None


def compare_medication_approaches(
    medication_name: str,
    sig_text: str,
    clinician_notes: str = "",
    interaction_notes: str = "",
) -> ComparisonResult:
    """Compare both approaches for medication interpretation."""

    input_data = {
        "medication_name": medication_name,
        "sig_text": sig_text,
        "clinician_notes": clinician_notes,
        "interaction_notes": interaction_notes,
    }

    # --- Approach 1: caremap (free-form + parsing) ---
    caremap_output = None
    caremap_error = None
    caremap_start = time.time()

    try:
        from caremap.llm_client import MedGemmaClient
        from caremap.medication_interpretation import interpret_medication_v3_grounded

        client = MedGemmaClient()
        result, _ = interpret_medication_v3_grounded(
            client=client,
            medication_name=medication_name,
            sig_text=sig_text,
            clinician_notes=clinician_notes,
            interaction_notes=interaction_notes,
        )
        caremap_output = result
    except Exception as e:
        caremap_error = str(e)

    caremap_time = (time.time() - caremap_start) * 1000

    # --- Approach 2: caremap_structured (outlines) ---
    structured_output = None
    structured_error = None
    structured_start = time.time()

    if OUTLINES_AVAILABLE:
        try:
            from caremap_structured.generators import (
                StructuredMedGemmaClient,
                generate_medication_output,
            )

            structured_client = StructuredMedGemmaClient()
            result = generate_medication_output(
                client=structured_client,
                medication_name=medication_name,
                sig_text=sig_text,
                clinician_notes=clinician_notes,
                interaction_notes=interaction_notes,
                version="v2",
            )
            structured_output = result.model_dump()
        except Exception as e:
            structured_error = str(e)
    else:
        structured_error = "outlines not installed"

    structured_time = (time.time() - structured_start) * 1000

    return ComparisonResult(
        input_data=input_data,
        caremap_output=caremap_output,
        caremap_error=caremap_error,
        caremap_time_ms=caremap_time,
        structured_output=structured_output,
        structured_error=structured_error,
        structured_time_ms=structured_time,
    )


def print_comparison_report(results: List[ComparisonResult]) -> None:
    """Print a comparison report for multiple test cases."""

    print("\n" + "=" * 70)
    print("COMPARISON REPORT: caremap vs caremap_structured")
    print("=" * 70)

    # Summary stats
    caremap_successes = sum(1 for r in results if r.caremap_succeeded)
    structured_successes = sum(1 for r in results if r.structured_succeeded)
    total = len(results)

    print(f"\nSUMMARY ({total} test cases)")
    print("-" * 40)
    print(f"{'Metric':<30} {'caremap':<15} {'structured':<15}")
    print("-" * 40)
    print(f"{'Success rate':<30} {caremap_successes}/{total:<12} {structured_successes}/{total:<12}")

    avg_caremap_time = sum(r.caremap_time_ms for r in results) / total
    avg_structured_time = sum(r.structured_time_ms for r in results) / total
    print(f"{'Avg time (ms)':<30} {avg_caremap_time:<15.0f} {avg_structured_time:<15.0f}")

    # Detailed results
    for i, result in enumerate(results, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}: {result.input_data.get('medication_name', 'Unknown')}")
        print("=" * 70)

        print(f"\nInput: {json.dumps(result.input_data, indent=2)[:200]}...")

        print(f"\n--- CAREMAP (free-form + parsing) ---")
        print(f"Time: {result.caremap_time_ms:.0f}ms")
        if result.caremap_error:
            print(f"ERROR: {result.caremap_error}")
        else:
            print(f"Output: {json.dumps(result.caremap_output, indent=2)[:500]}...")

        print(f"\n--- STRUCTURED (outlines) ---")
        print(f"Time: {result.structured_time_ms:.0f}ms")
        if result.structured_error:
            print(f"ERROR: {result.structured_error}")
        else:
            print(f"Output: {json.dumps(result.structured_output, indent=2)[:500]}...")


def print_critique() -> None:
    """Print a detailed critique of both approaches."""

    print("\n" + "=" * 70)
    print("CRITIQUE: WHICH APPROACH IS BETTER?")
    print("=" * 70)

    print("""
## caremap Approach (Current)

**How it works:**
1. Send prompt to MedGemma
2. Get free-form text response
3. Parse JSON using regex/brace matching
4. Validate against expected keys
5. Apply post-hoc safety checks

**Pros:**
+ Already implemented and working
+ Model has freedom to express reasoning
+ V3 grounded prompts show chain-of-thought
+ Easier to debug (can see raw output)
+ Works with any model without modification

**Cons:**
- JSON parsing can fail (~5-10% of the time)
- Extra keys or missing keys require retries
- No type safety at generation time
- Post-hoc validation is reactive, not preventive
- Wasted compute on invalid outputs

---

## caremap_structured Approach (Outlines)

**How it works:**
1. Define Pydantic schema
2. Outlines constrains token generation to match schema
3. Output is ALWAYS valid JSON matching schema
4. Type-safe Python objects returned directly

**Pros:**
+ 100% valid JSON (by construction)
+ Type-safe Pydantic objects
+ No parsing failures ever
+ Schema defines both structure AND validation
+ Cleaner code (no parse/validate dance)

**Cons:**
- Adds dependency (outlines)
- Model loading through outlines wrapper
- May constrain model's expressiveness
- Less visibility into model's "thinking"
- MPS (Apple Silicon) support may be limited
- Slower first-run (compiles FSM for schema)

---

## RECOMMENDATION

**For a competition/production system, I recommend a HYBRID approach:**

1. **Use outlines for structure** - Guarantees valid JSON, eliminates parse errors
2. **Keep safety validation separate** - SafetyValidator still checks for:
   - Forbidden medical terms
   - Jargon leakage
   - Measurement values
   - Negation preservation

3. **Pydantic schemas as single source of truth** - Define once, use for:
   - Outlines generation constraint
   - Response type hints
   - API documentation (FastAPI)
   - Test validation

**Migration path:**
- Phase 1: Add outlines as optional dependency
- Phase 2: Create structured generators alongside existing
- Phase 3: A/B test quality on golden scenarios
- Phase 4: Switch default if quality is maintained

**Key insight:** Outlines solves the STRUCTURE problem (valid JSON), but we still
need the SafetyValidator for the CONTENT problem (safe medical language).
""")


def demo_without_model() -> None:
    """Demo that runs without requiring model loading."""

    print("\n" + "=" * 70)
    print("DEMO: Schema Validation (No Model Required)")
    print("=" * 70)

    from caremap_structured.schemas import MedicationOutputV2, ImagingOutputV2

    # Show how Pydantic validates structure
    print("\n1. Valid MedicationOutputV2:")
    valid_med = MedicationOutputV2(
        medication="Metformin",
        what_this_does="Helps control blood sugar by improving insulin sensitivity.",
        how_to_give="Take one tablet twice daily with meals.",
        watch_out_for="Stop before CT scans with contrast dye.",
    )
    print(f"   {valid_med.model_dump_json(indent=2)}")

    print("\n2. Valid ImagingOutputV2:")
    valid_img = ImagingOutputV2(
        study_type="Chest CT",
        what_this_scan_does="Creates detailed pictures of the chest.",
        what_was_found="A small spot was found in the lung.",
        what_this_means="Needs follow-up in 3 months.",
        questions_for_doctor=["What could cause this spot?", "When is the next scan?"],
    )
    print(f"   {valid_img.model_dump_json(indent=2)}")

    print("\n3. Schema JSON (for outlines):")
    print(f"   MedicationOutputV2 schema: {MedicationOutputV2.model_json_schema()}")


def main():
    """Run comparison demo."""

    print("\n" + "#" * 70)
    print("# CAREMAP vs CAREMAP_STRUCTURED COMPARISON")
    print("#" * 70)

    # First, show schema validation without model
    demo_without_model()

    # Print the critique
    print_critique()

    # Check if we can run the full comparison
    if not OUTLINES_AVAILABLE:
        print("\n" + "=" * 70)
        print("NOTE: Install outlines to run full comparison")
        print("      pip install outlines")
        print("=" * 70)
        return

    # Ask user before running expensive model comparison
    print("\n" + "=" * 70)
    print("READY TO RUN FULL COMPARISON")
    print("This will load MedGemma twice (caremap + structured)")
    print("Estimated time: 2-5 minutes")
    print("=" * 70)

    response = input("\nRun full comparison? [y/N]: ").strip().lower()
    if response != "y":
        print("Skipping full comparison.")
        return

    # Run comparison on sample medications
    test_cases = [
        {
            "medication_name": "Metformin",
            "sig_text": "Take 500mg twice daily with meals",
            "clinician_notes": "For type 2 diabetes. Monitor kidney function.",
            "interaction_notes": "Hold 48h before/after CT with contrast.",
        },
        {
            "medication_name": "Warfarin",
            "sig_text": "Take 5mg daily at 6 PM",
            "clinician_notes": "For AFib. Target INR 2-3.",
            "interaction_notes": "Avoid NSAIDs, aspirin. Watch vitamin K intake.",
        },
    ]

    results = []
    for tc in test_cases:
        print(f"\nProcessing: {tc['medication_name']}...")
        result = compare_medication_approaches(**tc)
        results.append(result)

    print_comparison_report(results)


if __name__ == "__main__":
    main()
