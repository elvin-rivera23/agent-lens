"""
Base Agent Class

Abstract base class for all agents in the orchestration graph.
Provides common LLM calling logic via httpx to the inference service.
Supports MOCK_MODE for local testing without inference.
"""

import asyncio
import json
import logging
import os
import time
from abc import ABC, abstractmethod

import httpx
from events import broadcaster
from state import OrchestratorState
from telemetry import record_tokens, track_agent
from tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

# Mock mode for testing without inference service
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

# Mock responses for each agent type
MOCK_RESPONSES = {
    "architect": """{
    "summary": "Create a simple fibonacci function",
    "subtasks": [
        {"id": 1, "title": "Fibonacci Function", "description": "Implement fibonacci sequence generator", "dependencies": []}
    ]
}""",
    "coder": '''```python
def fibonacci(n):
    """Generate fibonacci sequence up to n terms."""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]

    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i-1] + fib[i-2])
    return fib

if __name__ == "__main__":
    result = fibonacci(10)
    print(f"Fibonacci sequence: {result}")
```''',
    "reviewer": "All checks passed. Code is syntactically correct and follows best practices.",
}


class BaseAgent(ABC):
    """
    Abstract base class for orchestration agents.

    Each agent has:
    - A unique name for identification and telemetry
    - A system prompt defining its role
    - An invoke method that processes state and returns updated state
    - Optional tool registry for function calling
    """

    name: str = "base"
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, tools: ToolRegistry | None = None):
        self.inference_url = os.getenv("INFERENCE_URL", "http://localhost:8000")
        self.timeout = float(os.getenv("AGENT_TIMEOUT", "60"))
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._tools = tools

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

    def get_tool_schemas(self) -> list[dict]:
        """Get OpenAI function schemas for registered tools."""
        if self._tools is None:
            return []
        return self._tools.get_schemas()

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a registered tool.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            ToolResult with success status and output
        """
        if self._tools is None:
            return ToolResult(
                success=False,
                output="",
                error="No tools registered for this agent",
            )

        logger.info(f"[{self.name}] Executing tool: {tool_name}")
        result = self._tools.execute(tool_name, **kwargs)

        if result.success:
            logger.info(f"[{self.name}] Tool {tool_name} succeeded")
        else:
            logger.warning(f"[{self.name}] Tool {tool_name} failed: {result.error}")

        return result

    def parse_tool_calls(self, response: str) -> list[dict]:
        """
        Parse tool calls from LLM response.

        Looks for JSON blocks with tool_call format:
        {"tool": "grep", "args": {"pattern": "def foo"}}

        Returns:
            List of tool call dicts with 'tool' and 'args' keys
        """
        tool_calls = []

        # Try to find tool call JSON blocks
        import re

        # Match ```json ... ``` or ```tool ... ``` blocks
        json_pattern = r"```(?:json|tool)?\s*(\{[^`]*?\})\s*```"
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match)
                if "tool" in data:
                    tool_calls.append({
                        "tool": data["tool"],
                        "args": data.get("args", {}),
                    })
            except json.JSONDecodeError:
                continue

        # Also try inline JSON without code blocks
        inline_pattern = r'\{"tool"\s*:\s*"(\w+)"[^}]*\}'
        for match in re.finditer(inline_pattern, response):
            try:
                data = json.loads(match.group(0))
                if "tool" in data and data not in tool_calls:
                    tool_calls.append({
                        "tool": data["tool"],
                        "args": data.get("args", {}),
                    })
            except json.JSONDecodeError:
                continue

        return tool_calls

    async def call_llm(self, messages: list[dict], max_tokens: int = 1024) -> str:
        """
        Call the inference service with OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response
        """
        # Mock mode - return canned responses
        if MOCK_MODE:
            logger.info(f"[{self.name}] MOCK_MODE: Returning canned response")
            await asyncio.sleep(0.5)  # Simulate some latency
            response = MOCK_RESPONSES.get(self.name, "Mock response for " + self.name)
            record_tokens(self.name, len(response.split()))
            return response

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
