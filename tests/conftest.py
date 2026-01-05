"""
AgentLens test fixtures and configuration.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add services to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "inference" / "src"))


@pytest.fixture
def inference_client():
    """Create a test client for the inference service."""
    from main import app

    return TestClient(app)


@pytest.fixture
def mock_model_loaded(monkeypatch):
    """Mock the model as loaded."""
    monkeypatch.setattr("main.model", "mock-model")
