"""
Inference Client Abstraction

Provides a unified interface for calling LLM inference services.
Supports multiple backends: llama-cpp-python (CPU) and vLLM (GPU).
"""

import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class InferenceRuntime(Enum):
    """Available inference runtimes."""

    LLAMA_CPP = "llama-cpp"
    VLLM = "vllm"
    AUTO = "auto"  # Auto-detect based on availability


@dataclass
class InferenceConfig:
    """Configuration for inference client."""

    url: str
    timeout: float = 60.0
    max_retries: int = 3
    initial_retry_delay: float = 1.0


@dataclass
class CompletionRequest:
    """Request for completion generation."""

    messages: list[dict]
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False
    model: str = "default"


@dataclass
class CompletionResponse:
    """Response from completion generation."""

    content: str
    usage: dict | None = None
    model: str = "unknown"
    finish_reason: str = "stop"


class BaseInferenceClient(ABC):
    """Abstract base class for inference clients."""

    def __init__(self, config: InferenceConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate a completion for the given request."""
        raise NotImplementedError

    @abstractmethod
    async def stream_complete(
        self, request: CompletionRequest
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens for the given request."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the inference service is healthy."""
        raise NotImplementedError

    @property
    @abstractmethod
    def runtime(self) -> InferenceRuntime:
        """Return the runtime type."""
        raise NotImplementedError


class LlamaCppClient(BaseInferenceClient):
    """Client for llama-cpp-python inference service."""

    @property
    def runtime(self) -> InferenceRuntime:
        return InferenceRuntime.LLAMA_CPP

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using llama-cpp-python."""
        payload = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

        response = await self._client.post(
            f"{self.config.url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage")

        return CompletionResponse(
            content=content,
            usage=usage,
            model=data.get("model", request.model),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    async def stream_complete(
        self, request: CompletionRequest
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens using llama-cpp-python."""
        payload = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            f"{self.config.url}/v1/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except (KeyError, json.JSONDecodeError):
                        continue

    async def health_check(self) -> bool:
        """Check if llama-cpp-python service is healthy."""
        try:
            response = await self._client.get(f"{self.config.url}/health")
            return response.status_code == 200
        except Exception:
            return False


class VLLMClient(BaseInferenceClient):
    """Client for vLLM inference service."""

    @property
    def runtime(self) -> InferenceRuntime:
        return InferenceRuntime.VLLM

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Generate completion using vLLM."""
        # vLLM uses OpenAI-compatible API
        payload = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

        response = await self._client.post(
            f"{self.config.url}/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage")

        return CompletionResponse(
            content=content,
            usage=usage,
            model=data.get("model", request.model),
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    async def stream_complete(
        self, request: CompletionRequest
    ) -> AsyncGenerator[str, None]:
        """Stream completion tokens using vLLM."""
        payload = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            f"{self.config.url}/v1/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except (KeyError, json.JSONDecodeError):
                        continue

    async def health_check(self) -> bool:
        """Check if vLLM service is healthy."""
        try:
            response = await self._client.get(f"{self.config.url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def get_model_info(self) -> dict | None:
        """Get information about loaded models (vLLM specific)."""
        try:
            response = await self._client.get(f"{self.config.url}/v1/models")
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None


class InferenceClientFactory:
    """Factory for creating inference clients with fallback support."""

    def __init__(
        self,
        primary_url: str | None = None,
        fallback_url: str | None = None,
        runtime: InferenceRuntime = InferenceRuntime.AUTO,
        timeout: float = 60.0,
    ):
        self.primary_url = primary_url or os.getenv("INFERENCE_URL", "http://localhost:8000")
        self.fallback_url = fallback_url or os.getenv("INFERENCE_FALLBACK_URL")
        self.runtime = runtime
        self.timeout = timeout

        self._primary_client: BaseInferenceClient | None = None
        self._fallback_client: BaseInferenceClient | None = None
        self._active_client: BaseInferenceClient | None = None

    async def get_client(self) -> BaseInferenceClient:
        """Get an inference client, with automatic fallback if needed."""
        # If we have an active client that's healthy, use it
        if self._active_client is not None:
            if await self._active_client.health_check():
                return self._active_client

        # Try primary client
        if self._primary_client is None:
            self._primary_client = self._create_client(self.primary_url)

        if await self._primary_client.health_check():
            self._active_client = self._primary_client
            logger.info(f"Using primary inference: {self._primary_client.runtime.value}")
            return self._active_client

        # Try fallback if available
        if self.fallback_url:
            if self._fallback_client is None:
                self._fallback_client = self._create_client(self.fallback_url)

            if await self._fallback_client.health_check():
                self._active_client = self._fallback_client
                logger.warning(
                    f"Primary inference unavailable, using fallback: "
                    f"{self._fallback_client.runtime.value}"
                )
                return self._active_client

        # No healthy client available, return primary and let caller handle errors
        logger.error("No healthy inference service available")
        self._active_client = self._primary_client
        return self._active_client

    def _create_client(self, url: str) -> BaseInferenceClient:
        """Create an inference client based on runtime setting."""
        config = InferenceConfig(url=url, timeout=self.timeout)

        if self.runtime == InferenceRuntime.LLAMA_CPP:
            return LlamaCppClient(config)
        elif self.runtime == InferenceRuntime.VLLM:
            return VLLMClient(config)
        else:
            # Auto-detect: default to vLLM for GPU profile, llama-cpp for CPU
            # The actual detection happens at runtime based on health checks
            # For now, check environment hint
            runtime_hint = os.getenv("INFERENCE_RUNTIME", "auto").lower()
            if runtime_hint == "vllm":
                return VLLMClient(config)
            else:
                return LlamaCppClient(config)

    async def close(self) -> None:
        """Close all clients."""
        if self._primary_client:
            await self._primary_client.close()
        if self._fallback_client:
            await self._fallback_client.close()


# Default factory instance
_default_factory: InferenceClientFactory | None = None


def get_inference_factory() -> InferenceClientFactory:
    """Get the default inference client factory."""
    global _default_factory
    if _default_factory is None:
        _default_factory = InferenceClientFactory()
    return _default_factory


async def get_inference_client() -> BaseInferenceClient:
    """Get an inference client from the default factory."""
    factory = get_inference_factory()
    return await factory.get_client()
