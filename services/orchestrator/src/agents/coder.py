"""
Coder Agent

Generates Python code based on user tasks and writes it to the sandboxed workspace.
This is one of the two core agents in the M3 Vertical Slice.
"""

import logging
import os
import re
from pathlib import Path

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState

logger = logging.getLogger(__name__)

# Sandboxed workspace directory
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))


class CoderAgent(BaseAgent):
    """
    Agent that generates Python code and writes it to files.

    Responsibilities:
    - Interpret the user's coding task
    - Generate clean, working Python code
    - Write the code to the sandboxed workspace
    - Handle retry scenarios with error context
    """

    name = "coder"
    system_prompt = """You are an expert Python code generator.

Given a coding task, you will:
1. Understand the requirements
2. Write clean, working Python code
3. Include a simple test/demo at the end that shows the code works

CRITICAL RULES - MUST FOLLOW:
- Output ONLY a single Python code block with ```python ... ```
- ALL code MUST be in a SINGLE FILE - no separate files, no project structure
- Do NOT create files, directories, or write to disk
- Do NOT import from local modules - only use standard library and common packages (pygame, requests, flask, numpy, etc)
- Make the code SELF-CONTAINED and immediately runnable with `python file.py`
- Include a main block that demonstrates the code works
- For games: use pygame and keep all code in one file
- For APIs: use Flask/FastAPI and keep all code in one file

Example output format:
```python
# Complete self-contained code here
def my_function():
    pass

if __name__ == "__main__":
    # Demo/test the code
    my_function()
```"""

    def __init__(self):
        super().__init__()
        # Workspace is created lazily in invoke() to avoid permission issues during import

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Generate code for the task and write it to the workspace.

        If this is a retry, include the previous error in the prompt.
        """
        # Build the prompt
        messages = self._build_messages(state)

        # Call LLM
        response = await self.call_llm(messages, max_tokens=2048)

        # Parse code from response
        code = self._extract_code(response)

        if not code:
            state.add_history(self.name, "generate", "Failed to extract code from response")
            raise ValueError("Could not extract Python code from LLM response")

        # Generate filename from task
        filename = self._generate_filename(state.task)
        file_path = WORKSPACE_DIR / filename

        # Ensure workspace exists (lazy creation)
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

        # Write code to file
        file_path.write_text(code, encoding="utf-8")
        logger.info(f"[{self.name}] Wrote {len(code)} chars to {file_path}")

        # Emit event for Glass-Box visibility
        await broadcaster.emit_code_written(self.name, str(file_path), len(code))

        # Update state
        state.code = code
        state.file_path = str(file_path)
        state.add_history(self.name, "generate", f"Wrote code to {file_path}")

        return state

    def _build_messages(self, state: OrchestratorState) -> list[dict]:
        """Build the message list for the LLM call."""
        messages = []

        # Use subtask description if available from Architect, else use original task
        task_description = state.get_current_subtask_description()

        task_prompt = f"Write Python code for the following task:\n\n{task_description}"

        # Include review feedback if this is a review fix
        if state.review_attempts > 0 and state.review_feedback and not state.review_passed:
            task_prompt += f"""

IMPORTANT: The previous code was rejected by the reviewer:
```
{state.review_feedback}
```

Please fix the code to address these issues."""

        # Include execution error if this is a runtime retry
        elif state.error_count > 0 and state.execution_output:
            task_prompt += f"""

IMPORTANT: The previous code attempt failed with this error:
```
{state.execution_output[:1000]}
```

Please fix the code to address this error."""

        messages.append({"role": "user", "content": task_prompt})

        return messages

    def _extract_code(self, response: str) -> str | None:
        """
        Extract Python code from LLM response.

        Looks for ```python ... ``` code blocks.
        """
        # Try to find python code block
        pattern = r"```python\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            return matches[0].strip()

        # Fallback: try generic code block
        pattern = r"```\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            return matches[0].strip()

        # Last resort: if no code blocks, check if entire response looks like code
        if "def " in response or "import " in response:
            return response.strip()

        return None

    def _generate_filename(self, task: str) -> str:
        """Generate a filename from the task description."""
        # Extract key words from task
        words = task.lower().split()

        # Filter to meaningful words
        stop_words = {
            "a",
            "an",
            "the",
            "write",
            "create",
            "make",
            "build",
            "python",
            "code",
            "function",
            "that",
            "which",
            "to",
            "for",
            "with",
        }
        meaningful = [w for w in words if w.isalnum() and w not in stop_words]

        # Take first 3 meaningful words
        name_parts = meaningful[:3] if meaningful else ["generated"]
        name = "_".join(name_parts)

        # Clean up and add extension
        name = re.sub(r"[^a-z0-9_]", "", name)

        return f"{name}.py"
