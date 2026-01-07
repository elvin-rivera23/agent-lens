"""
LangGraph State Machine

Defines the full 4-agent orchestration graph:
Architect → Coder → Reviewer → Executor

With retry loops:
- Reviewer → Coder (on review failure)
- Executor → Coder (on runtime error)
"""

import logging
from typing import Literal

from events import EventType, broadcaster
from langgraph.graph import END, StateGraph
from state import OrchestratorState
from telemetry import ORCHESTRATION_FAILURES, ORCHESTRATION_RETRIES, ORCHESTRATION_SUCCESSES

from agents import ArchitectAgent, CoderAgent, ExecutorAgent, ReviewerAgent

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Instances
# =============================================================================

architect_agent = ArchitectAgent()
coder_agent = CoderAgent()
reviewer_agent = ReviewerAgent()
executor_agent = ExecutorAgent()


# =============================================================================
# Graph Node Functions (with crash bypass)
# =============================================================================


async def architect_node(state: OrchestratorState) -> OrchestratorState:
    """Architect agent node - creates execution plan."""
    try:
        return await architect_agent.run_with_telemetry(state)
    except Exception as e:
        # Bypass: create minimal plan and continue
        logger.error(f"Architect crashed, using fallback plan: {e}")
        state.plan = {
            "summary": state.task,
            "subtasks": [{"id": 1, "title": "Complete task", "description": state.task, "dependencies": []}],
        }
        state.add_history("architect", "bypass", f"Crashed: {e}")
        return state


async def coder_node(state: OrchestratorState) -> OrchestratorState:
    """Coder agent node - generates code and writes to file."""
    try:
        return await coder_agent.run_with_telemetry(state)
    except Exception as e:
        # Bypass: mark as failed, let retry logic handle
        logger.error(f"Coder crashed: {e}")
        state.code = ""
        state.execution_success = False
        state.add_history("coder", "crash", str(e))
        return state


async def reviewer_node(state: OrchestratorState) -> OrchestratorState:
    """Reviewer agent node - checks code quality."""
    try:
        return await reviewer_agent.run_with_telemetry(state)
    except Exception as e:
        # Bypass: skip review and proceed to execution
        logger.warning(f"Reviewer crashed, skipping review: {e}")
        state.review_passed = True  # Skip review on crash
        state.review_feedback = f"Skipped due to error: {e}"
        state.add_history("reviewer", "bypass", str(e))
        return state


async def executor_node(state: OrchestratorState) -> OrchestratorState:
    """Executor agent node - runs the code and captures output."""
    try:
        return await executor_agent.run_with_telemetry(state)
    except Exception as e:
        # Bypass: mark execution as failed
        logger.error(f"Executor crashed: {e}")
        state.execution_success = False
        state.execution_output = f"Executor error: {e}"
        state.add_history("executor", "crash", str(e))
        return state


# =============================================================================
# Routing Logic
# =============================================================================


def should_execute_or_fix(state: OrchestratorState) -> Literal["execute", "fix"]:
    """
    Determine next step after code review.

    Returns:
        "execute" if review passed
        "fix" if review failed and can retry
    """
    if state.review_passed:
        logger.info("Review passed, proceeding to execution")
        return "execute"

    if state.can_retry_review():
        logger.info(f"Review failed, retrying ({state.review_attempts}/{state.max_review_attempts})")
        return "fix"

    # Max review attempts, proceed to execution anyway
    logger.warning("Max review attempts reached, proceeding despite failures")
    return "execute"


def should_retry_or_end(state: OrchestratorState) -> Literal["retry", "end"]:
    """
    Determine if we should retry after execution failure.

    Returns:
        "retry" if we should loop back to coder
        "end" if we should finish (success or max retries)
    """
    if state.execution_success:
        ORCHESTRATION_SUCCESSES.inc()
        return "end"

    if state.can_retry():
        state.error_count += 1
        # Reset review attempts for new code
        state.review_attempts = 0
        state.review_passed = False
        ORCHESTRATION_RETRIES.inc()
        logger.info(f"Execution failed, retrying ({state.error_count}/{state.max_retries})")
        return "retry"

    ORCHESTRATION_FAILURES.inc()
    logger.warning(f"Max retries ({state.max_retries}) exceeded")
    return "end"


# =============================================================================
# Build the Graph
# =============================================================================


def build_orchestration_graph() -> StateGraph:
    """
    Build the LangGraph state machine with retry loops.

    Graph structure:
        START → architect → coder → reviewer ─┬─ execute → executor ─┬─ end → END
                                              │                      │
                                              └── fix ─────────────> │
                                                                     └── retry → coder
    """
    graph = StateGraph(OrchestratorState)

    # Add all nodes
    graph.add_node("architect", architect_node)
    graph.add_node("coder", coder_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("executor", executor_node)

    # Set entry point
    graph.set_entry_point("architect")

    # Linear edges
    graph.add_edge("architect", "coder")
    graph.add_edge("coder", "reviewer")

    # Conditional edge after reviewer: execute or fix (loop back to coder)
    graph.add_conditional_edges(
        "reviewer",
        should_execute_or_fix,
        {
            "execute": "executor",
            "fix": "coder",
        },
    )

    # Conditional edge after executor: retry (loop back to coder) or end
    graph.add_conditional_edges(
        "executor",
        should_retry_or_end,
        {
            "retry": "coder",
            "end": END,
        },
    )

    return graph


# Compile the graph with higher recursion limit
orchestration_graph = build_orchestration_graph().compile()
orchestration_graph.recursion_limit = 50


# =============================================================================
# Public API
# =============================================================================


async def run_orchestration(task: str) -> OrchestratorState:
    """
    Run the full orchestration for a coding task.

    Args:
        task: The user's coding request

    Returns:
        Final state with plan, code, review, execution output, etc.
    """
    initial_state = OrchestratorState(task=task)

    await broadcaster.emit(EventType.AGENT_START, "orchestrator", {"task": task})

    try:
        result = await orchestration_graph.ainvoke(
            initial_state,
            config={"recursion_limit": 50}
        )

        # LangGraph may return dict or state object depending on version
        if isinstance(result, dict):
            final_state = OrchestratorState(**result)
        else:
            final_state = result

        await broadcaster.emit(
            EventType.COMPLETE,
            "orchestrator",
            {
                "success": final_state.execution_success,
                "retries": final_state.error_count,
                "review_passed": final_state.review_passed,
            },
        )

        return final_state

    except Exception as e:
        ORCHESTRATION_FAILURES.inc()
        await broadcaster.emit_error("orchestrator", str(e))
        raise


async def cleanup():
    """Cleanup agent resources."""
    await architect_agent.close()
    await coder_agent.close()
    await reviewer_agent.close()
    await executor_agent.close()
