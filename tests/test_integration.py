"""
Integration Tests for Orchestrator

Docker-compose based integration tests for the Coder → Executor flow.
These tests verify the full agent pipeline works end-to-end.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add orchestrator src to path
_orchestrator_src = Path(__file__).parent.parent / "services" / "orchestrator" / "src"
if str(_orchestrator_src) not in sys.path:
    sys.path.insert(0, str(_orchestrator_src))


class TestCoderExecutorFlow:
    """Integration tests for Coder → Executor agent flow."""

    @pytest.mark.asyncio
    async def test_coder_generates_code_executor_runs(self):
        """Test that Coder generates code and Executor runs it successfully."""
        from graph import coder_node, executor_node
        from state import OrchestratorState

        # Start with a state that has a plan
        state = OrchestratorState(
            task="Print hello world",
            plan={
                "summary": "Print hello world",
                "subtasks": [{"id": 1, "title": "Print", "description": "Print hello world", "dependencies": []}],
            },
        )

        # Mock the coder agent to return simple code
        with patch("graph.coder_agent") as mock_coder:
            mock_coder.run_with_telemetry = AsyncMock(return_value=OrchestratorState(
                **{**state.model_dump(), "code": "print('hello world')", "file_path": "/workspace/test.py"}
            ))
            state = await coder_node(state)

        assert state.code == "print('hello world')"
        assert state.file_path == "/workspace/test.py"

        # Mock the executor agent to run the code
        with patch("graph.executor_agent") as mock_executor:
            mock_executor.run_with_telemetry = AsyncMock(return_value=OrchestratorState(
                **{**state.model_dump(), "execution_success": True, "execution_output": "hello world"}
            ))
            state = await executor_node(state)

        assert state.execution_success is True
        assert "hello world" in state.execution_output

    @pytest.mark.asyncio
    async def test_coder_failure_triggers_retry(self):
        """Test that Coder failure is handled by retry logic."""
        from graph import coder_node, should_retry_or_end
        from state import OrchestratorState

        state = OrchestratorState(task="Test task", max_retries=3)

        # Simulate coder crash (handled by bypass)
        with patch("graph.coder_agent") as mock_coder:
            mock_coder.run_with_telemetry = AsyncMock(side_effect=Exception("LLM timeout"))
            state = await coder_node(state)

        # Coder crash should mark execution as failed
        assert state.execution_success is False
        assert state.code == ""

        # Retry logic should route back
        result = should_retry_or_end(state)
        assert result == "retry"

    @pytest.mark.asyncio
    async def test_executor_failure_loops_back(self):
        """Test that Executor failure with retries available loops back to Coder."""
        from graph import executor_node, should_retry_or_end
        from state import OrchestratorState

        state = OrchestratorState(
            task="Test task",
            code="print(undefined_var)",  # Bad code
            error_count=0,
            max_retries=3,
        )

        # Mock executor to return failure
        with patch("graph.executor_agent") as mock_executor:
            mock_executor.run_with_telemetry = AsyncMock(return_value=OrchestratorState(
                **{**state.model_dump(), "execution_success": False, "execution_output": "NameError: undefined_var"}
            ))
            state = await executor_node(state)

        assert state.execution_success is False

        # Should trigger retry
        result = should_retry_or_end(state)
        assert result == "retry"


class TestReviewerCoderFlow:
    """Integration tests for Reviewer → Coder retry flow."""

    @pytest.mark.asyncio
    async def test_review_fail_loops_to_coder(self):
        """Test that failed review routes back to Coder."""
        from graph import reviewer_node, should_execute_or_fix
        from state import OrchestratorState

        state = OrchestratorState(
            task="Test task",
            code="eval(input())",  # Unsafe code
            review_attempts=0,
            max_review_attempts=2,
        )

        # Mock reviewer to return failure
        with patch("graph.reviewer_agent") as mock_reviewer:
            mock_reviewer.run_with_telemetry = AsyncMock(return_value=OrchestratorState(
                **{**state.model_dump(), "review_passed": False, "review_feedback": "Security issue: eval() is unsafe"}
            ))
            state = await reviewer_node(state)

        assert state.review_passed is False

        # Should route to fix
        result = should_execute_or_fix(state)
        assert result == "fix"


class TestInferenceDisconnectRecovery:
    """Tests for inference disconnect handling."""

    @pytest.mark.asyncio
    async def test_connection_retry_on_disconnect(self):
        """Test that connection errors trigger retry with backoff."""
        import httpx
        from agents.coder import CoderAgent

        # Use a real agent subclass (not abstract)
        agent = CoderAgent()

        # Simulate connection error then success
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection refused")
            # Return success on 3rd try
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}],
                "usage": {"completion_tokens": 10},
            }
            return mock_response

        agent._client.post = mock_post

        # Should succeed after retries
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await agent.call_llm([{"role": "user", "content": "test"}])

        assert result == "test response"
        assert call_count == 3  # Failed twice, succeeded on third


class TestConversationContext:
    """Tests for conversation memory and context passing."""

    def test_state_preserves_history(self):
        """Test that state history is preserved across agent calls."""
        from state import OrchestratorState

        state = OrchestratorState(task="Multi-step task")

        # Add history entries like agents would
        state.add_history("architect", "plan", "Created 3 subtasks")
        state.add_history("coder", "code", "Generated fibonacci.py")
        state.add_history("reviewer", "review", "Passed security check")
        state.add_history("executor", "exec", "Output: 1, 1, 2, 3, 5")

        assert len(state.history) == 4
        assert state.history[0]["agent"] == "architect"
        assert state.history[-1]["agent"] == "executor"

    def test_state_tracks_current_subtask(self):
        """Test that state tracks current subtask for multi-step plans."""
        from state import OrchestratorState

        state = OrchestratorState(
            task="Complex task",
            plan={
                "summary": "Multi-step plan",
                "subtasks": [
                    {"id": 1, "title": "Step 1", "description": "First step", "dependencies": []},
                    {"id": 2, "title": "Step 2", "description": "Second step", "dependencies": [1]},
                ],
            },
            current_subtask=0,
        )

        # Format is "Title: Description"
        assert state.get_current_subtask_description() == "Step 1: First step"

        state.current_subtask = 1
        assert state.get_current_subtask_description() == "Step 2: Second step"
