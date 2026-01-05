"""
Orchestrator State Schema

Defines the state that flows between agents in the LangGraph.
"""

from pydantic import BaseModel, Field


class OrchestratorState(BaseModel):
    """State passed between agents in the orchestration graph."""

    # User request
    task: str = Field(..., description="The user's original coding task")

    # Coder agent outputs
    code: str = Field(default="", description="Generated Python code")
    file_path: str = Field(default="", description="Path where code was written")

    # Executor agent outputs
    execution_output: str = Field(default="", description="stdout/stderr from execution")
    execution_success: bool = Field(default=False, description="Whether execution succeeded")

    # Orchestration tracking
    current_agent: str = Field(default="", description="Currently active agent")
    error_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    # History for debugging
    history: list[dict] = Field(default_factory=list, description="Agent action history")

    def add_history(self, agent: str, action: str, result: str) -> None:
        """Add an entry to the action history."""
        self.history.append({"agent": agent, "action": action, "result": result})

    def can_retry(self) -> bool:
        """Check if we can retry after a failure."""
        return self.error_count < self.max_retries
