"""
AgentLens test fixtures and configuration.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def inference_client():
    """Create a test client for the inference service."""
    # Must use absolute import path to avoid conflicts with orchestrator's main.py
    inference_src = Path(__file__).parent.parent / "services" / "inference" / "src"

    # Temporarily insert at front of path
    sys.path.insert(0, str(inference_src))
    try:
        # Force reimport to get the inference module
        if "main" in sys.modules:
            # Remove cached main module if it exists
            del sys.modules["main"]
        if "config" in sys.modules:
            del sys.modules["config"]

        from main import app
        return TestClient(app)
    finally:
        # Clean up path
        if str(inference_src) in sys.path:
            sys.path.remove(str(inference_src))


@pytest.fixture
def mock_model_loaded(monkeypatch):
    """Mock the model as loaded."""
    monkeypatch.setattr("main.model", "mock-model")
