"""Tests for inference client abstraction."""

import pytest
from inference_client import (
    CompletionRequest,
    CompletionResponse,
    InferenceClientFactory,
    InferenceConfig,
    InferenceRuntime,
    LlamaCppClient,
    VLLMClient,
)


class TestInferenceConfig:
    """Tests for InferenceConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = InferenceConfig(url="http://localhost:8000")

        assert config.url == "http://localhost:8000"
        assert config.timeout == 60.0
        assert config.max_retries == 3
        assert config.initial_retry_delay == 1.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = InferenceConfig(
            url="http://custom:9000",
            timeout=120.0,
            max_retries=5,
            initial_retry_delay=2.0,
        )

        assert config.url == "http://custom:9000"
        assert config.timeout == 120.0
        assert config.max_retries == 5
        assert config.initial_retry_delay == 2.0


class TestCompletionRequest:
    """Tests for CompletionRequest."""

    def test_default_values(self):
        """Test default request values."""
        request = CompletionRequest(
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert request.max_tokens == 1024
        assert request.temperature == 0.7
        assert request.stream is False
        assert request.model == "default"


class TestCompletionResponse:
    """Tests for CompletionResponse."""

    def test_minimal_response(self):
        """Test response with minimal fields."""
        response = CompletionResponse(content="Hello world")

        assert response.content == "Hello world"
        assert response.usage is None
        assert response.model == "unknown"
        assert response.finish_reason == "stop"

    def test_full_response(self):
        """Test response with all fields."""
        response = CompletionResponse(
            content="Generated text",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            model="llama-3-8b",
            finish_reason="length",
        )

        assert response.content == "Generated text"
        assert response.usage["completion_tokens"] == 20
        assert response.model == "llama-3-8b"
        assert response.finish_reason == "length"


class TestLlamaCppClient:
    """Tests for LlamaCppClient."""

    def test_runtime_type(self):
        """Test that client reports correct runtime."""
        config = InferenceConfig(url="http://localhost:8000")
        client = LlamaCppClient(config)

        assert client.runtime == InferenceRuntime.LLAMA_CPP

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with unreachable server."""
        config = InferenceConfig(url="http://localhost:99999", timeout=0.5)
        client = LlamaCppClient(config)

        try:
            result = await client.health_check()
            assert result is False
        finally:
            await client.close()


class TestVLLMClient:
    """Tests for VLLMClient."""

    def test_runtime_type(self):
        """Test that client reports correct runtime."""
        config = InferenceConfig(url="http://localhost:8000")
        client = VLLMClient(config)

        assert client.runtime == InferenceRuntime.VLLM

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with unreachable server."""
        config = InferenceConfig(url="http://localhost:99999", timeout=0.5)
        client = VLLMClient(config)

        try:
            result = await client.health_check()
            assert result is False
        finally:
            await client.close()


class TestInferenceClientFactory:
    """Tests for InferenceClientFactory."""

    def test_default_url_from_env(self, monkeypatch):
        """Test factory uses environment variable for URL."""
        monkeypatch.setenv("INFERENCE_URL", "http://test:8000")

        factory = InferenceClientFactory()
        assert factory.primary_url == "http://test:8000"

    def test_explicit_url_override(self, monkeypatch):
        """Test explicit URL overrides environment."""
        monkeypatch.setenv("INFERENCE_URL", "http://env:8000")

        factory = InferenceClientFactory(primary_url="http://explicit:8000")
        assert factory.primary_url == "http://explicit:8000"

    def test_runtime_selection_llama_cpp(self):
        """Test runtime selection for llama-cpp."""
        factory = InferenceClientFactory(runtime=InferenceRuntime.LLAMA_CPP)
        client = factory._create_client("http://localhost:8000")

        assert isinstance(client, LlamaCppClient)

    def test_runtime_selection_vllm(self):
        """Test runtime selection for vLLM."""
        factory = InferenceClientFactory(runtime=InferenceRuntime.VLLM)
        client = factory._create_client("http://localhost:8000")

        assert isinstance(client, VLLMClient)

    def test_auto_runtime_default(self, monkeypatch):
        """Test auto runtime defaults to llama-cpp without hint."""
        monkeypatch.delenv("INFERENCE_RUNTIME", raising=False)

        factory = InferenceClientFactory(runtime=InferenceRuntime.AUTO)
        client = factory._create_client("http://localhost:8000")

        # Default should be llama-cpp for CPU compatibility
        assert isinstance(client, LlamaCppClient)

    def test_auto_runtime_vllm_hint(self, monkeypatch):
        """Test auto runtime respects vLLM hint."""
        monkeypatch.setenv("INFERENCE_RUNTIME", "vllm")

        factory = InferenceClientFactory(runtime=InferenceRuntime.AUTO)
        client = factory._create_client("http://localhost:8000")

        assert isinstance(client, VLLMClient)


class TestInferenceRuntime:
    """Tests for InferenceRuntime enum."""

    def test_all_runtimes_have_values(self):
        """Test all runtimes have string values."""
        for runtime in InferenceRuntime:
            assert isinstance(runtime.value, str)
            assert len(runtime.value) > 0

    def test_expected_runtimes(self):
        """Test expected runtime values exist."""
        assert InferenceRuntime.LLAMA_CPP.value == "llama-cpp"
        assert InferenceRuntime.VLLM.value == "vllm"
        assert InferenceRuntime.AUTO.value == "auto"
