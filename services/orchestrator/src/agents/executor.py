"""
Executor Agent

Executes Python code in a sandboxed environment and captures the output.
This is the second core agent in the M3 Vertical Slice.
"""

import asyncio
import logging
import os
from pathlib import Path

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState

logger = logging.getLogger(__name__)

# Execution constraints
EXECUTION_TIMEOUT = float(os.getenv("EXECUTION_TIMEOUT", "30"))
ALLOWED_COMMANDS = {"python", "python3", "pytest", "ruff"}


class ExecutorAgent(BaseAgent):
    """
    Agent that executes Python code and validates the output.

    Responsibilities:
    - Run the generated Python file
    - Capture stdout/stderr
    - Determine success/failure
    - Provide error context for retries

    Security:
    - Only executes files in /workspace
    - Command whitelist (python, pytest, ruff)
    - Execution timeout (default 30s)
    """

    name = "executor"
    system_prompt = "You are a code executor."  # Not used for LLM calls

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Execute the generated code and capture the result.
        """
        file_path = Path(state.file_path).resolve()

        # Validate file exists
        if not file_path.exists():
            error = f"File not found: {file_path}"
            state.execution_output = error
            state.execution_success = False
            state.add_history(self.name, "execute", error)
            await broadcaster.emit_error(self.name, error)
            return state

        # Validate file is in workspace (security)
        workspace = Path(os.getenv("WORKSPACE_DIR", "/workspace")).resolve()
        try:
            file_path.relative_to(workspace)
        except ValueError:
            # On Windows, paths may have different formats, try string comparison
            file_str = str(file_path).lower()
            workspace_str = str(workspace).lower()
            if not file_str.startswith(workspace_str):
                error = f"Security: File {file_path} is outside workspace"
                state.execution_output = error
                state.execution_success = False
                state.add_history(self.name, "execute", error)
                await broadcaster.emit_error(self.name, error)
                return state

        # Execute the file
        success, output, exit_code = await self._execute_python(file_path)

        # Update state
        state.execution_output = output
        state.execution_success = success
        state.add_history(self.name, "execute", f"exit_code={exit_code}, success={success}")

        # Emit execution event for Glass-Box visibility
        await broadcaster.emit_execution(self.name, success, output, exit_code)

        logger.info(f"[{self.name}] Execution {'succeeded' if success else 'failed'}: {output[:100]}")

        return state

    async def _execute_python(self, file_path: Path) -> tuple[bool, str, int]:
        """
        Execute a Python file and capture the output.

        Returns:
            Tuple of (success, output, exit_code)
        """
        import subprocess

        cmd = ["python", str(file_path)]

        # Validate command is in whitelist
        if cmd[0] not in ALLOWED_COMMANDS:
            return False, f"Command not allowed: {cmd[0]}", -1

        try:
            # Use subprocess.run for Windows compatibility
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT,
                cwd=file_path.parent,
            )

            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr

            success = result.returncode == 0
            return success, output.strip(), result.returncode

        except subprocess.TimeoutExpired:
            return False, f"Execution timed out after {EXECUTION_TIMEOUT}s", -1
        except Exception as e:
            logger.exception(f"[{self.name}] Execution error: {e}")
            return False, f"Execution error: {e}", -1
