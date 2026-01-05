"""
Orchestrator Tests

Unit and integration tests for the multi-agent orchestration system.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add orchestrator src to path for imports
orchestrator_src = Path(__file__).parent.parent / "services" / "orchestrator" / "src"
sys.path.insert(0, str(orchestrator_src))


class TestOrchestratorState:
    """Tests for OrchestratorState model."""

    def test_state_creation(self):
        """Test basic state creation."""
        from state import OrchestratorState

        state = OrchestratorState(task="Write hello world")

        assert state.task == "Write hello world"
        assert state.code == ""
        assert state.file_path == ""
        assert state.execution_success is False
        assert state.error_count == 0
        assert state.max_retries == 3

    def test_can_retry(self):
        """Test retry logic."""
        from state import OrchestratorState

        state = OrchestratorState(task="test", max_retries=2)

        assert state.can_retry() is True

        state.error_count = 1
        assert state.can_retry() is True

        state.error_count = 2
        assert state.can_retry() is False

    def test_add_history(self):
        """Test history tracking."""
        from state import OrchestratorState

        state = OrchestratorState(task="test")
        state.add_history("coder", "generate", "success")

        assert len(state.history) == 1
        assert state.history[0]["agent"] == "coder"
        assert state.history[0]["action"] == "generate"


class TestCoderAgent:
    """Tests for CoderAgent code parsing and file generation."""

    def test_extract_python_code_block(self):
        """Test extraction of Python code from markdown."""
        from agents.coder import CoderAgent

        agent = CoderAgent()

        response = '''Here is the code:
```python
def hello():
    return "world"
```
That should work!'''

        code = agent._extract_code(response)
        assert code is not None
        assert "def hello():" in code
        assert 'return "world"' in code

    def test_extract_generic_code_block(self):
        """Test extraction of generic code block."""
        from agents.coder import CoderAgent

        agent = CoderAgent()

        response = '''```
def test():
    pass
```'''

        code = agent._extract_code(response)
        assert code is not None
        assert "def test():" in code

    def test_extract_no_code_block(self):
        """Test fallback when no code block present."""
        from agents.coder import CoderAgent

        agent = CoderAgent()

        # Response with code-like content but no markdown
        response = "def fibonacci(n):\n    return n"
        code = agent._extract_code(response)
        assert code is not None

        # Response with no code at all
        response = "I don't understand the question."
        code = agent._extract_code(response)
        assert code is None

    def test_generate_filename(self):
        """Test filename generation from task."""
        from agents.coder import CoderAgent

        agent = CoderAgent()

        # Normal task
        filename = agent._generate_filename("Write a fibonacci function")
        assert filename.endswith(".py")
        assert "fibonacci" in filename

        # Task with special characters
        filename = agent._generate_filename("Create a func! that does @#$")
        assert filename.endswith(".py")

        # Empty meaningful words
        filename = agent._generate_filename("Write a code")
        assert filename == "generated.py"


class TestExecutorAgent:
    """Tests for ExecutorAgent command execution."""

    def test_command_whitelist(self):
        """Test that only whitelisted commands are allowed."""
        from agents.executor import ALLOWED_COMMANDS

        assert "python" in ALLOWED_COMMANDS
        assert "python3" in ALLOWED_COMMANDS
        assert "pytest" in ALLOWED_COMMANDS
        assert "ruff" in ALLOWED_COMMANDS
        assert "rm" not in ALLOWED_COMMANDS
        assert "curl" not in ALLOWED_COMMANDS

    @pytest.mark.asyncio
    async def test_execute_simple_python(self, tmp_path):
        """Test executing a simple Python file."""
        from agents.executor import ExecutorAgent

        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text('print("Hello, World!")')

        agent = ExecutorAgent()

        # Mock the workspace check
        with patch.dict("os.environ", {"WORKSPACE_DIR": str(tmp_path)}):
            success, output, exit_code = await agent._execute_python(test_file)

        assert success is True
        assert "Hello, World!" in output
        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_python_error(self, tmp_path):
        """Test executing Python code with error."""
        from agents.executor import ExecutorAgent

        # Create a test file with syntax error
        test_file = tmp_path / "error.py"
        test_file.write_text("def broken(:\n    pass")

        agent = ExecutorAgent()

        with patch.dict("os.environ", {"WORKSPACE_DIR": str(tmp_path)}):
            success, output, exit_code = await agent._execute_python(test_file)

        assert success is False
        assert exit_code != 0


class TestGraphRouting:
    """Tests for LangGraph routing logic."""

    def test_should_retry_on_success(self):
        """Test that successful execution ends the graph."""
        from graph import should_retry
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=True,
        )

        result = should_retry(state)
        assert result == "end"

    def test_should_retry_on_failure(self):
        """Test that failure triggers retry."""
        from graph import should_retry
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=False,
            error_count=0,
            max_retries=3,
        )

        result = should_retry(state)
        assert result == "retry"
        assert state.error_count == 1

    def test_should_end_on_max_retries(self):
        """Test that max retries ends the graph."""
        from graph import should_retry
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=False,
            error_count=3,
            max_retries=3,
        )

        result = should_retry(state)
        assert result == "end"


class TestTelemetry:
    """Tests for telemetry and metrics."""

    @pytest.mark.asyncio
    async def test_track_agent_context_manager(self):
        """Test the track_agent context manager."""
        from telemetry import track_agent

        async with track_agent("test_agent"):
            await asyncio.sleep(0.01)

        # If we get here without error, the context manager worked


class TestEvents:
    """Tests for WebSocket event broadcasting."""

    def test_agent_event_serialization(self):
        """Test event JSON serialization."""
        from events import AgentEvent, EventType

        event = AgentEvent(
            type=EventType.AGENT_START,
            agent="coder",
            data={"task": "test"},
        )

        json_str = event.to_json()
        assert '"type": "agent_start"' in json_str
        assert '"agent": "coder"' in json_str
        assert '"task": "test"' in json_str
