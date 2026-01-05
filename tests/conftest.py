"""
AgentLens test fixtures and configuration.
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Cache the inference client at module level to avoid Prometheus registry conflicts
_inference_client = None


@pytest.fixture
def inference_client():
    """Create a test client for the inference service.

    Uses module-level caching to avoid reimporting the app
    which causes Prometheus registry conflicts.
    """
    global _inference_client

    if _inference_client is not None:
        return _inference_client

    # Add inference src to path
    inference_src = Path(__file__).parent.parent / "services" / "inference" / "src"
    sys.path.insert(0, str(inference_src))

    try:
        from main import app

        _inference_client = TestClient(app)
        return _inference_client
    finally:
        # Clean up path but keep client cached
        if str(inference_src) in sys.path:
            sys.path.remove(str(inference_src))


@pytest.fixture
def mock_model_loaded(monkeypatch):
    """Mock the model as loaded."""
    monkeypatch.setattr("main.model", "mock-model")
