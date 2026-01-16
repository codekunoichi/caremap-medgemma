"""
Shared pytest fixtures for CareMap tests.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_medgemma_client():
    """
    Create a mock MedGemmaClient that returns predictable JSON responses.
    """
    mock_client = MagicMock()

    def generate_side_effect(prompt: str) -> str:
        # Return different JSON based on prompt content
        # Check for lab prompt first (more specific patterns)
        if "TEST_NAME" in prompt or "meaning_category" in prompt.lower():
            return '''{"what_was_checked": "Blood test.", "what_it_means": "Normal result.", "what_to_ask_doctor": "Is this okay?"}'''
        elif "MEDICATION_NAME" in prompt or "medication_name" in prompt.lower():
            return '''{"medication": "TestMed", "why_it_matters": "Helps with condition.", "when_to_give": "Morning", "important_note": ""}'''
        elif "ITEM_TEXT" in prompt or "time_bucket" in prompt.lower():
            return '''{"time_bucket": "Today", "action_item": "Schedule appointment.", "next_step": "Call clinic"}'''
        else:
            return '''{"result": "ok"}'''

    mock_client.generate.side_effect = generate_side_effect
    return mock_client


@pytest.fixture
def sample_canonical_patient_v11():
    """
    Sample patient data in v1.1 EHR-aligned schema format.
    """
    return {
        "meta": {
            "source": "CCDA",
            "generated_on": "2026-01-15",
            "language": "en"
        },
        "patient": {
            "nickname": "TestPatient",
            "age_range": "60s",
            "sex": "F",
            "conditions_display": ["Diabetes", "High blood pressure", "Heart disease"]
        },
        "medications": [
            {
                "medication_name": "Metformin",
                "sig_text": "Take 1 tablet twice daily",
                "timing": "morning and evening",
                "clinician_notes": "Take with food",
                "interaction_notes": ""
            },
            {
                "medication_name": "Lisinopril",
                "sig_text": "Take 1 tablet daily",
                "timing": "",
                "clinician_notes": "",
                "interaction_notes": ""
            }
        ],
        "results": [
            {
                "test_name": "A1c",
                "meaning_category": "Needs follow-up",
                "flag": "high",
                "source_note": "Above target"
            }
        ],
        "care_gaps": [
            {
                "item_text": "Eye exam overdue",
                "next_step": "Call clinic",
                "time_bucket": "This Week"
            },
            {
                "item_text": "Blood work due",
                "next_step": "Schedule lab",
                "time_bucket": "Today"
            }
        ],
        "contacts": {
            "clinic_name": "Test Clinic",
            "clinic_phone": "555-1234",
            "pharmacy_name": "Test Pharmacy",
            "pharmacy_phone": "555-5678"
        }
    }


@pytest.fixture
def minimal_canonical_patient():
    """
    Minimal patient data with sparse fields to test fail-closed behavior.
    """
    return {
        "meta": {"language": "en"},
        "medications": [
            {"medication_name": "Aspirin"}
        ],
        "results": [],
        "care_gaps": [],
        "contacts": {}
    }
