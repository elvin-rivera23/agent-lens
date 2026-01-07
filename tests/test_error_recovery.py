"""
Error Recovery Tests

Tests for the M4 Production Hardening crash bypass and retry logic.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add orchestrator src to path
_orchestrator_src = Path(__file__).parent.parent / "services" / "orchestrator" / "src"
if str(_orchestrator_src) not in sys.path:
    sys.path.insert(0, str(_orchestrator_src))


class TestCrashBypass:
    """Tests for agent crash bypass handlers in graph nodes."""

    @pytest.mark.asyncio
    async def test_architect_crash_returns_fallback_plan(self):
        """Test that architect crash creates a fallback plan."""
        from graph import architect_node
        from state import OrchestratorState

        state = OrchestratorState(task="Write hello world")

        # Mock architect_agent to raise an exception
        with patch("graph.architect_agent") as mock_agent:
            mock_agent.run_with_telemetry = AsyncMock(side_effect=Exception("LLM timeout"))

            result = await architect_node(state)

        # Should return with a fallback plan, not raise
        assert result.plan is not None
        assert "subtasks" in result.plan
        assert len(result.plan["subtasks"]) == 1
        assert any("bypass" in h["action"] for h in result.history)

    @pytest.mark.asyncio
    async def test_reviewer_crash_skips_review(self):
        """Test that reviewer crash skips review and proceeds."""
        from graph import reviewer_node
        from state import OrchestratorState

        state = OrchestratorState(task="Test task", code="print('hello')")

        with patch("graph.reviewer_agent") as mock_agent:
            mock_agent.run_with_telemetry = AsyncMock(side_effect=Exception("Parse error"))

            result = await reviewer_node(state)

        # Should skip review on crash
        assert result.review_passed is True
        assert "Skipped due to error" in result.review_feedback
        assert any("bypass" in h["action"] for h in result.history)

    @pytest.mark.asyncio
    async def test_coder_crash_marks_failure(self):
        """Test that coder crash marks execution as failed for retry."""
        from graph import coder_node
        from state import OrchestratorState

        state = OrchestratorState(task="Test task")

        with patch("graph.coder_agent") as mock_agent:
            mock_agent.run_with_telemetry = AsyncMock(side_effect=Exception("Model OOM"))

            result = await coder_node(state)

        # Should mark as failed, not raise
        assert result.execution_success is False
        assert result.code == ""
        assert any("crash" in h["action"] for h in result.history)

    @pytest.mark.asyncio
    async def test_executor_crash_marks_failure(self):
        """Test that executor crash marks execution as failed."""
        from graph import executor_node
        from state import OrchestratorState

        state = OrchestratorState(task="Test task", code="print('test')")

        with patch("graph.executor_agent") as mock_agent:
            mock_agent.run_with_telemetry = AsyncMock(side_effect=Exception("Sandbox error"))

            result = await executor_node(state)

        # Should mark as failed, not raise
        assert result.execution_success is False
        assert "Executor error" in result.execution_output
        assert any("crash" in h["action"] for h in result.history)


class TestConditionalEdges:
    """Tests for conditional edge routing logic."""

    def test_review_fix_loops_back_to_coder(self):
        """Test that failed review with retries routes to 'fix' (coder)."""
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

    def test_execution_retry_loops_back_to_coder(self):
        """Test that failed execution with retries routes to 'retry' (coder)."""
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
        assert state.error_count == 1  # Should increment
        assert state.review_attempts == 0  # Should reset


class TestErrorClassification:
    """Tests for error classification integration."""

    def test_json_parse_error_classified_as_parse(self):
        """Test that JSON decode errors are classified correctly."""
        from errors import ErrorCategory, ErrorClassifier

        classifier = ErrorClassifier()
        error = classifier.classify("json.decoder.JSONDecodeError: Expecting value: line 1")

        assert error.category == ErrorCategory.PARSE

    def test_connection_error_classified_correctly(self):
        """Test that connection errors are classified correctly."""
        from errors import ErrorCategory, ErrorClassifier

        classifier = ErrorClassifier()
        error = classifier.classify("httpx.ConnectError: Connection refused")

        assert error.category == ErrorCategory.CONNECTION

    def test_timeout_error_classified_correctly(self):
        """Test that timeout errors are classified correctly."""
        from errors import ErrorCategory, ErrorClassifier

        classifier = ErrorClassifier()
        error = classifier.classify("asyncio.TimeoutError: timed out waiting for response")

        assert error.category == ErrorCategory.TIMEOUT
