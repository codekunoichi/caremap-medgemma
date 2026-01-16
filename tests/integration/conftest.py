"""Fixtures for integration tests with real MedGemma client.

These tests use the actual MedGemma model to validate that the interpretation
functions produce outputs that meet golden specifications.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add src to path so caremap module can be imported
_SRC_DIR = Path(__file__).parent.parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Add tests to path so helpers can be imported
_TESTS_DIR = Path(__file__).parent.parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


@pytest.fixture(scope="session")
def medgemma_client():
    """Create a real MedGemma client for integration tests.

    This fixture is session-scoped to avoid reinitializing the model
    for each test (model loading is expensive).

    Returns:
        MedGemmaClient instance with auto-detected device
    """
    from caremap.llm_client import MedGemmaClient

    # Create client with automatic device detection
    # Will use CUDA if available, then MPS, then CPU
    client = MedGemmaClient()
    return client
