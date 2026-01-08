"""
Orchestrator State Schema

Defines the state that flows between agents in the LangGraph.
"""

from pydantic import BaseModel, Field


class FileSpec(BaseModel):
    """Specification for a file to be generated."""
    path: str = Field(..., description="Relative file path (e.g., 'src/main.py')")
    description: str = Field(default="", description="What this file should contain")
    content: str = Field(default="", description="Generated file content")
    generated: bool = Field(default=False, description="Whether file has been generated")


class ExecutionStep(BaseModel):
    """A single execution step."""
    cmd: str = Field(..., description="Command to run")
    label: str = Field(default="", description="Human-readable label for this step")
    background: bool = Field(default=False, description="Run in background (for servers)")
    port: int | None = Field(default=None, description="Port exposed if background server")
    requires_approval: bool = Field(default=False, description="Needs user approval before running")


class ExecutionPlan(BaseModel):
    """Plan for how to execute the generated project."""
    steps: list[ExecutionStep] = Field(default_factory=list, description="Commands to run")
    preview_type: str = Field(default="terminal", description="'terminal', 'iframe', or 'none'")
    preview_url: str = Field(default="", description="URL for iframe preview if applicable")


class OrchestratorState(BaseModel):
    """State passed between agents in the orchestration graph."""

    # User request
    task: str = Field(..., description="The user's original coding task")

    # Architect agent outputs - Multi-file plan
    plan: dict = Field(default_factory=dict, description="Structured execution plan")
    planned_files: list[FileSpec] = Field(default_factory=list, description="Files to generate")
    execution_plan: ExecutionPlan | None = Field(default=None, description="How to run the project")
    current_file_index: int = Field(default=0, description="Index of current file being generated")
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
    preview_url: str = Field(default="", description="URL for live preview if web app")

    # Orchestration tracking
    current_agent: str = Field(default="", description="Currently active agent")
    error_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    # History for debugging
    history: list[dict] = Field(default_factory=list, description="Agent action history")

    # Conversation memory / context passing
    messages: list[dict] = Field(
        default_factory=list,
        description="Conversation messages for context passing between agents"
    )
    context_tokens: int = Field(default=0, description="Estimated token count of context")
    max_context_tokens: int = Field(default=4096, description="Max context tokens before compression")
    context_compressed: bool = Field(default=False, description="Whether context was compressed")

    # Multi-file workspace tracking
    workspace_files: dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative file paths to content for all generated files"
    )

    def add_file(self, file_path: str, content: str) -> None:
        """Add or update a file in the workspace tracking."""
        self.workspace_files[file_path] = content

    def add_history(self, agent: str, action: str, result: str) -> None:
        """Add an entry to the action history."""
        self.history.append({"agent": agent, "action": action, "result": result})

    def add_message(self, role: str, content: str, agent: str | None = None) -> None:
        """Add a message to conversation memory for context passing."""
        message = {"role": role, "content": content}
        if agent:
            message["agent"] = agent
        self.messages.append(message)
        # Rough token estimate: ~4 chars per token
        self.context_tokens += len(content) // 4

    def get_context_messages(self, max_messages: int = 10) -> list[dict]:
        """Get recent messages for context, with optional limit."""
        return self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages

    def should_compress_context(self) -> bool:
        """Check if context should be compressed due to token limit."""
        return self.context_tokens > self.max_context_tokens

    def compress_context(self, keep_recent: int = 5) -> None:
        """Compress context by keeping only recent messages and summarizing old ones."""
        if len(self.messages) <= keep_recent:
            return

        # Keep system messages and recent messages
        old_messages = self.messages[:-keep_recent]
        recent_messages = self.messages[-keep_recent:]

        # Create a summary of old messages
        summary_parts = []
        for msg in old_messages:
            agent = msg.get("agent", msg.get("role", "unknown"))
            content = msg.get("content", "")[:100]  # Truncate long content
            summary_parts.append(f"[{agent}]: {content}...")

        summary = "\n".join(summary_parts)
        summary_message = {
            "role": "system",
            "content": f"Previous conversation summary:\n{summary}",
            "compressed": True,
        }

        self.messages = [summary_message] + recent_messages
        self.context_tokens = sum(len(m.get("content", "")) // 4 for m in self.messages)
        self.context_compressed = True

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
