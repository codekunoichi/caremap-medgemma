"""
Pytest fixtures for CareMap integration tests.

These fixtures provide a real MedGemma client for testing
against golden specifications.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def medgemma_client():
    """
    Real MedGemma client - created once per test session.

    This loads the actual google/medgemma-4b-it model.
    Scope is "session" to avoid reloading the model for each test.

    Requirements:
    - HuggingFace authentication (for gated model access)
    - GPU recommended (CPU works but is slow)
    - ~8GB VRAM or ~16GB RAM
    """
    from caremap.llm_client import MedGemmaClient

    print("\n[FIXTURE] Loading MedGemma client (session-scoped)...")
    client = MedGemmaClient()
    print(f"[FIXTURE] MedGemma loaded on device: {client.device}")

    return client


@pytest.fixture(scope="session")
def safety_validator():
    """
    SafetyValidator instance for checking outputs.
    """
    from caremap.safety_validator import SafetyValidator

    return SafetyValidator(strict_mode=True)
