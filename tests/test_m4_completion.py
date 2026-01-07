"""
Tests for M4 Completion: Context, OOM Fallback, and Disconnect Handling

These tests verify the remaining M4 production hardening features.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add orchestrator src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "orchestrator" / "src"))

from inference_client import (
    TIERED_MODELS,
    CompletionRequest,
    CompletionResponse,
    InferenceClientFactory,
    KVCacheStats,
    OOMError,
)
from state import OrchestratorState


class TestConversationMemory:
    """Tests for conversation memory and context passing."""

    def test_add_message(self):
        """Test adding messages to conversation memory."""
        state = OrchestratorState(task="test task")
        state.add_message("user", "Hello", agent="user")
        state.add_message("assistant", "Hi there!", agent="architect")

        assert len(state.messages) == 2
        assert state.messages[0]["role"] == "user"
        assert state.messages[0]["content"] == "Hello"
        assert state.messages[1]["agent"] == "architect"

    def test_context_token_estimation(self):
        """Test token estimation for context."""
        state = OrchestratorState(task="test")
        # Add a message with ~100 chars = ~25 tokens
        state.add_message("user", "a" * 100)

        assert state.context_tokens >= 20  # ~4 chars per token

    def test_get_context_messages_limit(self):
        """Test getting limited context messages."""
        state = OrchestratorState(task="test")
        for i in range(15):
            state.add_message("user", f"Message {i}")

        # Get last 5 messages
        recent = state.get_context_messages(max_messages=5)
        assert len(recent) == 5
        assert "Message 14" in recent[-1]["content"]

    def test_should_compress_context(self):
        """Test context compression trigger."""
        state = OrchestratorState(task="test", max_context_tokens=100)
        # Add messages until over limit
        for _ in range(10):
            state.add_message("user", "a" * 200)  # ~50 tokens each

        assert state.should_compress_context() is True

    def test_compress_context(self):
        """Test context compression."""
        state = OrchestratorState(task="test")
        for i in range(10):
            state.add_message("user", f"Long message number {i} with content")

        state.compress_context(keep_recent=3)

        # Should have summary + 3 recent
        assert len(state.messages) == 4
        assert state.context_compressed is True
        assert "summary" in state.messages[0]["content"].lower()


class TestKVCacheTracking:
    """Tests for KV cache utilization tracking."""

    def test_kv_cache_stats_dataclass(self):
        """Test KVCacheStats dataclass."""
        stats = KVCacheStats(
            used_blocks=100,
            total_blocks=200,
            utilization_percent=50.0,
            gpu_memory_used_mb=4096,
            gpu_memory_total_mb=16384,
        )

        assert stats.used_blocks == 100
        assert stats.utilization_percent == 50.0

    def test_update_kv_cache_stats(self):
        """Test updating KV cache stats from metrics."""
        factory = InferenceClientFactory()
        factory.update_kv_cache_stats({
            "num_used_gpu_blocks": 50,
            "num_total_gpu_blocks": 100,
            "gpu_cache_usage_perc": 0.5,
            "gpu_memory_total": 16000,
        })

        stats = factory.get_kv_cache_stats()
        assert stats.used_blocks == 50
        assert stats.total_blocks == 100
        assert stats.utilization_percent == 50.0


class TestTieredModelSelection:
    """Tests for tiered model selection based on VRAM."""

    def test_tiered_models_config(self):
        """Test tiered models configuration exists."""
        assert "large" in TIERED_MODELS
        assert "medium" in TIERED_MODELS
        assert "small" in TIERED_MODELS

    def test_get_recommended_model_large_vram(self):
        """Test model recommendation for large VRAM."""
        factory = InferenceClientFactory()
        config = factory.get_recommended_model(24.0)  # 24GB

        assert config["min_vram_gb"] <= 24.0

    def test_get_recommended_model_medium_vram(self):
        """Test model recommendation for medium VRAM."""
        factory = InferenceClientFactory()
        config = factory.get_recommended_model(12.0)  # 12GB

        assert config["min_vram_gb"] <= 12.0

    def test_get_recommended_model_small_vram(self):
        """Test model recommendation for small VRAM."""
        factory = InferenceClientFactory()
        config = factory.get_recommended_model(6.0)  # 6GB

        assert config["min_vram_gb"] <= 6.0


class TestOOMFallback:
    """Tests for OOM fallback logic."""

    @pytest.mark.asyncio
    async def test_oom_triggers_tier_downgrade(self):
        """Test that OOM error triggers model tier downgrade."""
        factory = InferenceClientFactory()
        factory._current_tier = "large"

        request = CompletionRequest(messages=[{"role": "user", "content": "test"}])

        # Mock client that raises OOM
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.complete = AsyncMock(side_effect=[
            Exception("CUDA out of memory"),
            CompletionResponse(content="success"),
        ])

        with patch.object(factory, "get_client", return_value=mock_client):
            with patch.object(factory, "_create_client", return_value=mock_client):
                factory._primary_client = mock_client
                factory._active_client = mock_client

                response = await factory.complete_with_fallback(request)

        assert factory._current_tier == "medium"
        assert response.content == "success"

    @pytest.mark.asyncio
    async def test_max_oom_fallbacks_exceeded(self):
        """Test that exceeding max OOM fallbacks raises error."""
        factory = InferenceClientFactory()
        factory._oom_count = 3  # Already at max

        request = CompletionRequest(messages=[{"role": "user", "content": "test"}])

        # Mock client that raises OOM
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.complete = AsyncMock(side_effect=Exception("CUDA out of memory"))

        with patch.object(factory, "get_client", return_value=mock_client):
            factory._primary_client = mock_client
            factory._active_client = mock_client

            with pytest.raises(OOMError):
                await factory.complete_with_fallback(request)


class TestInferenceDisconnect:
    """Tests for inference disconnect and queue handling."""

    def test_request_queue_initialization(self):
        """Test request queue is initialized."""
        factory = InferenceClientFactory()

        assert factory._request_queue == []
        assert factory._max_queue_size == 10
        assert factory._reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_disconnect_queues_request(self):
        """Test that disconnect queues the request."""
        factory = InferenceClientFactory()

        request = CompletionRequest(messages=[{"role": "user", "content": "test"}])

        # Mock client that raises connection error then succeeds
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(side_effect=[True, False, True])
        mock_client.complete = AsyncMock(side_effect=[
            Exception("Connection refused"),
            CompletionResponse(content="success"),
        ])

        with patch.object(factory, "get_client", return_value=mock_client):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                factory._primary_client = mock_client
                factory._active_client = mock_client

                await factory.complete_with_fallback(request)

        assert factory._reconnect_attempts >= 1

    @pytest.mark.asyncio
    async def test_process_queue(self):
        """Test processing queued requests."""
        factory = InferenceClientFactory()

        # Add requests to queue
        factory._request_queue = [
            CompletionRequest(messages=[{"role": "user", "content": "req1"}]),
            CompletionRequest(messages=[{"role": "user", "content": "req2"}]),
        ]

        # Mock successful client
        mock_client = MagicMock()
        mock_client.health_check = AsyncMock(return_value=True)
        mock_client.complete = AsyncMock(return_value=CompletionResponse(content="done"))

        with patch.object(factory, "get_client", return_value=mock_client):
            results = await factory.process_queue()

        assert len(results) == 2
        assert factory._request_queue == []
