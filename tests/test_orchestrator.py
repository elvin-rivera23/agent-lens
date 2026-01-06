"""
Orchestrator Tests

Unit and integration tests for the multi-agent orchestration system.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Orchestrator path - added to sys.path for imports
_orchestrator_src = Path(__file__).parent.parent / "services" / "orchestrator" / "src"


@pytest.fixture(autouse=True, scope="module")
def setup_orchestrator_path():
    """Add orchestrator src to path for module imports, clean up after."""
    sys.path.insert(0, str(_orchestrator_src))
    yield
    if str(_orchestrator_src) in sys.path:
        sys.path.remove(str(_orchestrator_src))


# For the tests that import at function level, we need path available now
# This is a workaround for pytest's collection phase
if str(_orchestrator_src) not in sys.path:
    sys.path.insert(0, str(_orchestrator_src))


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
        from graph import should_retry_or_end
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=True,
        )

        result = should_retry_or_end(state)
        assert result == "end"

    def test_should_retry_on_failure(self):
        """Test that failure triggers retry."""
        from graph import should_retry_or_end
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=False,
            error_count=0,
            max_retries=3,
        )

        result = should_retry_or_end(state)
        assert result == "retry"
        assert state.error_count == 1

    def test_should_end_on_max_retries(self):
        """Test that max retries ends the graph."""
        from graph import should_retry_or_end
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            execution_success=False,
            error_count=3,
            max_retries=3,
        )

        result = should_retry_or_end(state)
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


class TestArchitectAgent:
    """Tests for ArchitectAgent plan parsing."""

    def test_parse_plan_json(self):
        """Test parsing a valid JSON plan."""
        from agents.architect import ArchitectAgent

        agent = ArchitectAgent()

        response = '''{
            "summary": "Create a hello world app",
            "subtasks": [
                {"id": 1, "title": "Main function", "description": "Create main", "dependencies": []}
            ]
        }'''

        plan = agent._parse_plan(response)
        assert plan is not None
        assert plan["summary"] == "Create a hello world app"
        assert len(plan["subtasks"]) == 1

    def test_parse_plan_in_code_block(self):
        """Test parsing JSON wrapped in code block."""
        from agents.architect import ArchitectAgent

        agent = ArchitectAgent()

        response = '''Here is the plan:
```json
{
    "summary": "Test plan",
    "subtasks": [{"id": 1, "title": "Task 1", "description": "Do thing", "dependencies": []}]
}
```'''

        plan = agent._parse_plan(response)
        assert plan is not None
        assert plan["summary"] == "Test plan"

    def test_parse_plan_invalid(self):
        """Test parsing invalid response returns None."""
        from agents.architect import ArchitectAgent

        agent = ArchitectAgent()

        response = "I don't understand what you want."
        plan = agent._parse_plan(response)
        assert plan is None


class TestReviewerAgent:
    """Tests for ReviewerAgent code checks."""

    def test_syntax_check_valid(self):
        """Test syntax check on valid code."""
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()

        code = """
def hello():
    return "world"
"""
        ok, error = agent._check_syntax(code)
        assert ok is True
        assert error == ""

    def test_syntax_check_invalid(self):
        """Test syntax check on invalid code."""
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()

        code = "def broken(:\n    pass"
        ok, error = agent._check_syntax(code)
        assert ok is False
        assert "syntax" in error.lower() or "Line" in error

    def test_security_check_eval(self):
        """Test security check detects eval."""
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()

        code = 'result = eval("1 + 2")'
        issues = agent._check_security(code)
        assert len(issues) > 0
        assert any("eval" in issue for issue in issues)

    def test_security_check_clean(self):
        """Test security check on clean code."""
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()

        code = """
import math

def calculate(x):
    return math.sqrt(x)
"""
        issues = agent._check_security(code)
        assert len(issues) == 0


class TestNewStateFields:
    """Tests for new state fields added in M3.5."""

    def test_state_has_plan_fields(self):
        """Test state has architect fields."""
        from state import OrchestratorState

        state = OrchestratorState(task="test")
        assert state.plan == {}
        assert state.current_subtask == 0

    def test_state_has_review_fields(self):
        """Test state has reviewer fields."""
        from state import OrchestratorState

        state = OrchestratorState(task="test")
        assert state.review_passed is False
        assert state.review_feedback == ""
        assert state.review_attempts == 0
        assert state.max_review_attempts == 2

    def test_can_retry_review(self):
        """Test review retry logic."""
        from state import OrchestratorState

        state = OrchestratorState(task="test", max_review_attempts=2)
        assert state.can_retry_review() is True

        state.review_attempts = 1
        assert state.can_retry_review() is True

        state.review_attempts = 2
        assert state.can_retry_review() is False

    def test_get_current_subtask_description(self):
        """Test getting subtask description from plan."""
        from state import OrchestratorState

        state = OrchestratorState(task="Original task")

        # No plan - should return original task
        assert state.get_current_subtask_description() == "Original task"

        # With plan
        state.plan = {
            "summary": "Test",
            "subtasks": [
                {"id": 1, "title": "First", "description": "Do first thing"},
                {"id": 2, "title": "Second", "description": "Do second thing"},
            ],
        }
        assert "First" in state.get_current_subtask_description()

        state.current_subtask = 1
        assert "Second" in state.get_current_subtask_description()


class TestNewGraphRouting:
    """Tests for new graph routing in M3.5."""

    def test_should_execute_on_review_pass(self):
        """Test that passed review goes to executor."""
        from graph import should_execute_or_fix
        from state import OrchestratorState

        state = OrchestratorState(task="test", review_passed=True)
        result = should_execute_or_fix(state)
        assert result == "execute"

    def test_should_fix_on_review_fail(self):
        """Test that failed review goes back to coder."""
        from graph import should_execute_or_fix
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            review_passed=False,
            review_attempts=0,
            max_review_attempts=2,
        )
        result = should_execute_or_fix(state)
        assert result == "fix"

    def test_should_execute_on_max_review_attempts(self):
        """Test that max review attempts proceeds to execute."""
        from graph import should_execute_or_fix
        from state import OrchestratorState

        state = OrchestratorState(
            task="test",
            review_passed=False,
            review_attempts=2,
            max_review_attempts=2,
        )
        result = should_execute_or_fix(state)
        assert result == "execute"

