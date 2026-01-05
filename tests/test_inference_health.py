"""
Tests for inference service health and metrics endpoints.
"""


def test_health_endpoint(inference_client):
    """Test that health endpoint returns healthy status."""
    response = inference_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mode"] == "cpu"


def test_metrics_endpoint(inference_client):
    """Test that metrics endpoint returns Prometheus metrics."""
    response = inference_client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    # Check for expected metric names
    content = response.text
    assert "inference_requests_total" in content
    assert "inference_latency_seconds" in content


def test_completions_endpoint(inference_client):
    """Test the completions endpoint with a basic request."""
    response = inference_client.post(
        "/v1/completions",
        json={
            "prompt": "Hello, world!",
            "max_tokens": 50,
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "usage" in data
