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
from errors import (
    CONNECTION_RETRY_POLICY,
    JSON_PARSE_RETRY_POLICY,
    ErrorClassifier,
    RecoveryStrategy,
    get_fix_prompt,
)
from events import broadcaster
from state import OrchestratorState
from telemetry import record_tokens, track_agent
from tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


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
        self._tokens_used = 0  # Track tokens per invocation for telemetry

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    def _get_mock_response(self, messages: list[dict]) -> str:
        """Return mock LLM response for demo mode."""
        import random
        import asyncio
        
        # Simulate delay for realism
        time.sleep(random.uniform(0.5, 1.5))
        self._tokens_used = random.randint(150, 400)
        
        # Agent-specific mock responses
        if self.name == "architect":
            return """I'll break this task into steps:

## Implementation Plan

1. **Core functionality** - Implement the main logic
2. **User interface** - Create command-line interface  
3. **Data persistence** - Add JSON file storage
4. **Error handling** - Handle edge cases

The coder agent should create a single Python file with all functionality."""

        elif self.name == "coder":
            return '''```python
"""
Todo List Manager - Demo Generated Code
A command-line todo application with JSON persistence.
"""

import json
import os
from typing import Optional

class TodoManager:
    """Manages todo items with persistence."""
    
    def __init__(self, filepath: str = "todos.json"):
        self.filepath = filepath
        self.todos: list[dict] = []
        self.load()
    
    def load(self) -> None:
        """Load todos from JSON file."""
        if os.path.exists(self.filepath):
            with open(self.filepath, "r") as f:
                self.todos = json.load(f)
    
    def save(self) -> None:
        """Save todos to JSON file."""
        with open(self.filepath, "w") as f:
            json.dump(self.todos, f, indent=2)
    
    def add(self, task: str) -> int:
        """Add a new todo item."""
        todo_id = len(self.todos) + 1
        self.todos.append({
            "id": todo_id,
            "task": task,
            "completed": False
        })
        self.save()
        return todo_id
    
    def remove(self, todo_id: int) -> bool:
        """Remove a todo by ID."""
        for i, todo in enumerate(self.todos):
            if todo["id"] == todo_id:
                self.todos.pop(i)
                self.save()
                return True
        return False
    
    def complete(self, todo_id: int) -> bool:
        """Mark a todo as complete."""
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo["completed"] = True
                self.save()
                return True
        return False
    
    def list_all(self) -> list[dict]:
        """Return all todos."""
        return self.todos

def main():
    """Demo the TodoManager."""
    manager = TodoManager()
    
    # Add some todos
    print("Adding todos...")
    manager.add("Learn Python")
    manager.add("Build an app")
    manager.add("Deploy to production")
    
    # List todos
    print("\\nCurrent todos:")
    for todo in manager.list_all():
        status = "✓" if todo["completed"] else "○"
        print(f"  {status} [{todo['id']}] {todo['task']}")
    
    # Complete one
    manager.complete(1)
    print("\\nAfter completing first task:")
    for todo in manager.list_all():
        status = "✓" if todo["completed"] else "○"
        print(f"  {status} [{todo['id']}] {todo['task']}")

if __name__ == "__main__":
    main()
```'''

        elif self.name == "reviewer":
            return """## Code Review

**APPROVED** ✓

The code meets quality standards:
- Clean class-based structure
- Proper JSON persistence
- Good error handling
- Clear documentation

Minor suggestions for future:
- Add input validation
- Consider async file operations for larger datasets

Code is ready for execution."""

        elif self.name == "executor":
            return "Execution completed successfully."
        
        else:
            return f"Mock response from {self.name} agent."


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

        Includes automatic retry with exponential backoff for connection errors.
        Supports MOCK_LLM=true for demo without inference service.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response

        Raises:
            Exception: If all retries are exhausted
        """
        # Mock mode for demos without inference service
        if os.getenv("MOCK_LLM", "").lower() == "true":
            return self._get_mock_response(messages)
        
        # Prepend system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}, *messages]

        # Model name - default to tinyllama for Ollama
        model_name = os.getenv("INFERENCE_MODEL", "tinyllama")

        payload = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        classifier = ErrorClassifier()
        last_error = None

        # Retry loop with exponential backoff for connection errors
        for attempt in range(CONNECTION_RETRY_POLICY.max_retries + 1):
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
                    self._tokens_used += tokens  # Track for later emission

                duration = time.perf_counter() - start_time
                logger.info(f"[{self.name}] LLM call completed in {duration:.2f}s")

                return content

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadTimeout) as e:
                last_error = e
                classified = classifier.classify(e)

                if classified.recovery_strategy == RecoveryStrategy.RECONNECT:
                    if attempt < CONNECTION_RETRY_POLICY.max_retries:
                        delay = CONNECTION_RETRY_POLICY.get_delay(attempt)
                        logger.warning(
                            f"[{self.name}] Connection error, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{CONNECTION_RETRY_POLICY.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue

                logger.error(f"[{self.name}] LLM call failed after retries: {e}")
                raise

            except httpx.HTTPStatusError as e:
                logger.error(f"[{self.name}] LLM call failed: {e.response.status_code}")
                raise

            except Exception as e:
                logger.error(f"[{self.name}] LLM call error: {e}")
                raise

        # All retries exhausted
        if last_error:
            raise last_error
        raise RuntimeError("LLM call failed with no error captured")

    async def call_llm_streaming(
        self, 
        messages: list[dict], 
        max_tokens: int = 1024,
        file_path: str = "/output.py"
    ) -> str:
        """
        Call the inference service with streaming, emitting TOKEN events.

        Streams tokens to the dashboard via WebSocket for live display.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            file_path: File path to associate with tokens (for dashboard display)

        Returns:
            The complete generated text response
        """
        from events import EventType
        
        # Prepend system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}, *messages]

        # Model name - default to tinyllama for Ollama
        model_name = os.getenv("INFERENCE_MODEL", "tinyllama")

        payload = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "stream": True,
        }

        start_time = time.perf_counter()
        full_response = ""

        try:
            async with self._client.stream(
                "POST",
                f"{self.inference_url}/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta:
                                token = delta["content"]
                                full_response += token
                                
                                # Emit TOKEN event for live dashboard display
                                await broadcaster.emit(
                                    EventType.TOKEN,
                                    self.name,
                                    {"token": token, "file_path": file_path}
                                )
                        except json.JSONDecodeError:
                            continue

            duration = time.perf_counter() - start_time
            logger.info(f"[{self.name}] Streaming LLM call completed in {duration:.2f}s")

            return full_response

        except Exception as e:
            logger.error(f"[{self.name}] Streaming LLM call failed: {e}")
            # Fallback to non-streaming
            logger.info(f"[{self.name}] Falling back to non-streaming call")
            return await self.call_llm(messages, max_tokens)

    async def call_llm_with_json_retry(
        self,
        messages: list[dict],
        parse_func: callable,
        max_tokens: int = 1024,
    ) -> tuple[str, any]:
        """
        Call LLM and parse response as JSON with automatic retry on parse failure.

        Args:
            messages: List of message dicts
            parse_func: Function to parse/validate the JSON response
            max_tokens: Maximum tokens to generate

        Returns:
            Tuple of (raw_response, parsed_result)

        Raises:
            ValueError: If parsing fails after all retries
        """
        last_error = None

        for attempt in range(JSON_PARSE_RETRY_POLICY.max_retries + 1):
            response = await self.call_llm(messages, max_tokens)

            try:
                parsed = parse_func(response)
                if parsed is not None:
                    return response, parsed
                # parse_func returned None, treat as parse failure
                raise ValueError("Parser returned None")

            except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
                last_error = e
                classifier = ErrorClassifier()
                classified = classifier.classify(e)

                if attempt < JSON_PARSE_RETRY_POLICY.max_retries:
                    # Add fix prompt to messages
                    fix_prompt = get_fix_prompt(classified)
                    messages = [
                        *messages,
                        {"role": "assistant", "content": response},
                        {"role": "user", "content": fix_prompt},
                    ]
                    logger.warning(
                        f"[{self.name}] JSON parse failed, requesting fix "
                        f"(attempt {attempt + 1}/{JSON_PARSE_RETRY_POLICY.max_retries})"
                    )
                    continue

                logger.error(f"[{self.name}] JSON parse failed after retries: {e}")
                raise ValueError(f"Failed to parse JSON after retries: {e}") from e

        # Should not reach here, but just in case
        raise ValueError(f"JSON parse failed: {last_error}")

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
            await broadcaster.emit_agent_end(self.name, True, duration, self._tokens_used)
            # Reset for next invocation
            self._tokens_used = 0
            return result

        except Exception as e:
            duration = time.perf_counter() - start_time
            await broadcaster.emit_agent_end(self.name, False, duration, self._tokens_used)
            self._tokens_used = 0  # Reset for next invocation
            await broadcaster.emit_error(self.name, str(e))
            raise
