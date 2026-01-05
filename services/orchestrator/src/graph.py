"""
LangGraph State Machine

Defines the orchestration graph: Coder → Executor with retry loop.
"""

import logging
from typing import Literal

from events import EventType, broadcaster
from langgraph.graph import END, StateGraph
from state import OrchestratorState
from telemetry import ORCHESTRATION_FAILURES, ORCHESTRATION_RETRIES, ORCHESTRATION_SUCCESSES

from agents import CoderAgent, ExecutorAgent

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Instances
# =============================================================================

coder_agent = CoderAgent()
executor_agent = ExecutorAgent()


# =============================================================================
# Graph Node Functions
# =============================================================================


async def coder_node(state: OrchestratorState) -> OrchestratorState:
    """Coder agent node - generates code and writes to file."""
    return await coder_agent.run_with_telemetry(state)


async def executor_node(state: OrchestratorState) -> OrchestratorState:
    """Executor agent node - runs the code and captures output."""
    return await executor_agent.run_with_telemetry(state)


# =============================================================================
# Routing Logic
# =============================================================================


def should_retry(state: OrchestratorState) -> Literal["retry", "end"]:
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
        # Increment error count for next iteration
        state.error_count += 1
        ORCHESTRATION_RETRIES.inc()
        logger.info(f"Retrying... attempt {state.error_count}/{state.max_retries}")
        return "retry"

    # Max retries exceeded
    ORCHESTRATION_FAILURES.inc()
    logger.warning(f"Max retries ({state.max_retries}) exceeded")
    return "end"


# =============================================================================
# Build the Graph
# =============================================================================


def build_orchestration_graph() -> StateGraph:
    """
    Build the LangGraph state machine.

    Graph structure:
        START → coder → executor → [retry decision]
                  ↑________________________|
                        (on failure)
    """
    # Create graph with state schema
    graph = StateGraph(OrchestratorState)

    # Add nodes
    graph.add_node("coder", coder_node)
    graph.add_node("executor", executor_node)

    # Set entry point
    graph.set_entry_point("coder")

    # Add edges
    graph.add_edge("coder", "executor")

    # Conditional edge from executor
    graph.add_conditional_edges(
        "executor",
        should_retry,
        {
            "retry": "coder",  # Loop back on failure
            "end": END,  # Finish on success or max retries
        },
    )

    return graph


# Compile the graph
orchestration_graph = build_orchestration_graph().compile()


# =============================================================================
# Public API
# =============================================================================


async def run_orchestration(task: str) -> OrchestratorState:
    """
    Run the full orchestration for a coding task.

    Args:
        task: The user's coding request

    Returns:
        Final state with code, execution output, etc.
    """
    # Initialize state
    initial_state = OrchestratorState(task=task)

    # Emit start event
    await broadcaster.emit(EventType.AGENT_START, "orchestrator", {"task": task})

    try:
        # Run the graph
        final_state = await orchestration_graph.ainvoke(initial_state)

        # Emit completion event
        await broadcaster.emit(
            EventType.COMPLETE,
            "orchestrator",
            {
                "success": final_state.execution_success,
                "retries": final_state.error_count,
            },
        )

        return final_state

    except Exception as e:
        ORCHESTRATION_FAILURES.inc()
        await broadcaster.emit_error("orchestrator", str(e))
        raise


async def cleanup():
    """Cleanup agent resources."""
    await coder_agent.close()
    await executor_agent.close()
