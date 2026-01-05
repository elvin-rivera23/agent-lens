"""
Base Agent Class

Abstract base class for all agents in the orchestration graph.
Provides common LLM calling logic via httpx to the inference service.
"""

import logging
import os
import time
from abc import ABC, abstractmethod

import httpx
from events import broadcaster
from state import OrchestratorState
from telemetry import record_tokens, track_agent

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for orchestration agents.

    Each agent has:
    - A unique name for identification and telemetry
    - A system prompt defining its role
    - An invoke method that processes state and returns updated state
    """

    name: str = "base"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self):
        self.inference_url = os.getenv("INFERENCE_URL", "http://inference:8000")
        self.timeout = float(os.getenv("AGENT_TIMEOUT", "60"))
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    @abstractmethod
    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Execute the agent's logic and return updated state.

        Must be implemented by subclasses.
        """
        raise NotImplementedError

    async def call_llm(self, messages: list[dict], max_tokens: int = 1024) -> str:
        """
        Call the inference service with OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response
        """
        # Prepend system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}, *messages]

        payload = {
            "model": "default",
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        start_time = time.perf_counter()

        try:
            response = await self._client.post(
                f"{self.inference_url}/v1/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Extract response text
            content = data["choices"][0]["message"]["content"]

            # Record token usage for Glass-Box metrics
            if "usage" in data:
                tokens = data["usage"].get("completion_tokens", 0)
                record_tokens(self.name, tokens)

            duration = time.perf_counter() - start_time
            logger.info(f"[{self.name}] LLM call completed in {duration:.2f}s")

            return content

        except httpx.TimeoutException:
            logger.error(f"[{self.name}] LLM call timed out after {self.timeout}s")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[{self.name}] LLM call failed: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"[{self.name}] LLM call error: {e}")
            raise

    async def run_with_telemetry(self, state: OrchestratorState) -> OrchestratorState:
        """
        Run the agent with full telemetry tracking.

        This wraps invoke() with:
        - Prometheus metrics (via track_agent)
        - WebSocket event broadcasting
        - Error handling
        """
        start_time = time.perf_counter()

        # Emit start event
        await broadcaster.emit_agent_start(self.name, state.task)

        try:
            async with track_agent(self.name):
                # Update current agent in state
                state.current_agent = self.name

                # Run the actual agent logic
                result = await self.invoke(state)

            duration = time.perf_counter() - start_time
            await broadcaster.emit_agent_end(self.name, True, duration)
            return result

        except Exception as e:
            duration = time.perf_counter() - start_time
            await broadcaster.emit_agent_end(self.name, False, duration)
            await broadcaster.emit_error(self.name, str(e))
            raise
