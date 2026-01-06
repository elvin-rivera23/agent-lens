"""
Orchestrator State Schema

Defines the state that flows between agents in the LangGraph.
"""

from pydantic import BaseModel, Field


class OrchestratorState(BaseModel):
    """State passed between agents in the orchestration graph."""

    # User request
    task: str = Field(..., description="The user's original coding task")

    # Architect agent outputs
    plan: dict = Field(default_factory=dict, description="Structured execution plan")
    current_subtask: int = Field(default=0, description="Index of current subtask")

    # Coder agent outputs
    code: str = Field(default="", description="Generated Python code")
    file_path: str = Field(default="", description="Path where code was written")

    # Reviewer agent outputs
    review_passed: bool = Field(default=False, description="Whether code review passed")
    review_feedback: str = Field(default="", description="Review feedback/issues")
    review_attempts: int = Field(default=0, description="Number of review attempts")
    max_review_attempts: int = Field(default=2, description="Max review attempts before skip")

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

    def can_retry_review(self) -> bool:
        """Check if we can retry after a failed review."""
        return self.review_attempts < self.max_review_attempts

    def get_current_subtask_description(self) -> str:
        """Get the description of the current subtask for the coder."""
        if not self.plan or "subtasks" not in self.plan:
            return self.task

        subtasks = self.plan["subtasks"]
        if self.current_subtask < len(subtasks):
            subtask = subtasks[self.current_subtask]
            return f"{subtask.get('title', '')}: {subtask.get('description', '')}"

        return self.task
