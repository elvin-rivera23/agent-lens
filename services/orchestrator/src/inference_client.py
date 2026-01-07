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


@dataclass
class KVCacheStats:
    """KV cache utilization statistics from vLLM."""

    used_blocks: int = 0
    total_blocks: int = 0
    utilization_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0


# Tiered model configurations based on VRAM
TIERED_MODELS = {
    "large": {  # 24GB+ VRAM
        "model": "meta-llama/Llama-3.1-8B-Instruct",
        "max_model_len": 8192,
        "min_vram_gb": 20,
    },
    "medium": {  # 12-24GB VRAM
        "model": "microsoft/phi-2",
        "max_model_len": 2048,
        "min_vram_gb": 8,
    },
    "small": {  # 8-12GB VRAM
        "model": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "max_model_len": 2048,
        "min_vram_gb": 4,
    },
}


class InferenceError(Exception):
    """Base exception for inference errors."""

    pass


class OOMError(InferenceError):
    """CUDA out of memory error."""

    pass


class CUDAUnavailableError(InferenceError):
    """CUDA is not available."""

    pass


class InferenceDisconnectError(InferenceError):
    """Inference service disconnected."""

    pass


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

        # OOM fallback tracking
        self._oom_count: int = 0
        self._max_oom_fallbacks: int = 2
        self._current_tier: str = "large"

        # Disconnect queue for retry
        self._request_queue: list[CompletionRequest] = []
        self._max_queue_size: int = 10
        self._reconnect_attempts: int = 0
        self._max_reconnect_attempts: int = 5

        # KV cache stats (populated from vLLM metrics)
        self._kv_cache_stats: KVCacheStats = KVCacheStats()

    async def get_client(self) -> BaseInferenceClient:
        """Get an inference client, with automatic fallback if needed."""
        # If we have an active client that's healthy, use it
        if self._active_client is not None:
            if await self._active_client.health_check():
                self._reconnect_attempts = 0  # Reset on successful health check
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

    async def complete_with_fallback(
        self, request: CompletionRequest
    ) -> CompletionResponse:
        """Execute completion with OOM fallback and disconnect handling."""
        try:
            client = await self.get_client()
            response = await client.complete(request)
            self._oom_count = 0  # Reset on success
            return response
        except Exception as e:
            error_msg = str(e).lower()

            # Check for OOM errors
            if "out of memory" in error_msg or "oom" in error_msg or "cuda" in error_msg:
                return await self._handle_oom_error(request, e)

            # Check for disconnect errors
            if "connection" in error_msg or "timeout" in error_msg:
                return await self._handle_disconnect(request, e)

            raise

    async def _handle_oom_error(
        self, request: CompletionRequest, original_error: Exception
    ) -> CompletionResponse:
        """Handle OOM by falling back to smaller model tier."""
        self._oom_count += 1

        if self._oom_count > self._max_oom_fallbacks:
            logger.error("Max OOM fallbacks exceeded, giving up")
            raise OOMError(f"Exceeded max OOM fallbacks: {original_error}")

        # Downgrade to smaller tier
        tiers = list(TIERED_MODELS.keys())
        current_idx = tiers.index(self._current_tier) if self._current_tier in tiers else 0
        if current_idx < len(tiers) - 1:
            self._current_tier = tiers[current_idx + 1]
            logger.warning(f"OOM detected, falling back to tier: {self._current_tier}")

            # Update request with smaller model
            tier_config = TIERED_MODELS[self._current_tier]
            request.model = tier_config["model"]

            # Retry with smaller model
            client = await self.get_client()
            return await client.complete(request)
        else:
            raise OOMError(f"No smaller model tier available: {original_error}")

    async def _handle_disconnect(
        self, request: CompletionRequest, original_error: Exception
    ) -> CompletionResponse:
        """Handle disconnect by queuing request and attempting reconnect."""
        self._reconnect_attempts += 1

        if self._reconnect_attempts > self._max_reconnect_attempts:
            logger.error("Max reconnect attempts exceeded")
            raise InferenceDisconnectError(
                f"Exceeded max reconnect attempts: {original_error}"
            )

        # Queue the request
        if len(self._request_queue) < self._max_queue_size:
            self._request_queue.append(request)
            logger.info(f"Request queued, queue size: {len(self._request_queue)}")

        # Exponential backoff
        import asyncio
        delay = min(2 ** self._reconnect_attempts, 30)
        logger.info(f"Waiting {delay}s before reconnect attempt {self._reconnect_attempts}")
        await asyncio.sleep(delay)

        # Try to reconnect
        self._active_client = None  # Force re-check
        client = await self.get_client()

        if await client.health_check():
            logger.info("Reconnected successfully, processing queued request")
            return await client.complete(request)
        else:
            raise InferenceDisconnectError(f"Failed to reconnect: {original_error}")

    async def process_queue(self) -> list[CompletionResponse]:
        """Process any queued requests after reconnection."""
        results = []
        while self._request_queue:
            request = self._request_queue.pop(0)
            try:
                client = await self.get_client()
                response = await client.complete(request)
                results.append(response)
            except Exception as e:
                logger.error(f"Failed to process queued request: {e}")
        return results

    def get_recommended_model(self, available_vram_gb: float) -> dict:
        """Get recommended model configuration based on available VRAM."""
        for tier_name, config in TIERED_MODELS.items():
            if available_vram_gb >= config["min_vram_gb"]:
                logger.info(f"Recommended tier for {available_vram_gb}GB VRAM: {tier_name}")
                return config
        # Fallback to smallest
        return TIERED_MODELS["small"]

    def get_kv_cache_stats(self) -> KVCacheStats:
        """Get current KV cache statistics."""
        return self._kv_cache_stats

    def update_kv_cache_stats(self, stats: dict) -> None:
        """Update KV cache stats from vLLM metrics response."""
        self._kv_cache_stats = KVCacheStats(
            used_blocks=stats.get("num_used_gpu_blocks", 0),
            total_blocks=stats.get("num_total_gpu_blocks", 0),
            utilization_percent=(
                stats.get("num_used_gpu_blocks", 0)
                / max(stats.get("num_total_gpu_blocks", 1), 1)
                * 100
            ),
            gpu_memory_used_mb=stats.get("gpu_cache_usage_perc", 0) * 100,
            gpu_memory_total_mb=stats.get("gpu_memory_total", 0),
        )

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

