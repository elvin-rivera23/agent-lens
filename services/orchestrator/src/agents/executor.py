"""
Executor Agent - Universal Builder

Runs ANY command from the Architect's execution plan.
Handles pip, npm, terraform, docker, shell scripts, and more.
Streams output to dashboard via WebSocket.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState

logger = logging.getLogger(__name__)

# Execution constraints
EXECUTION_TIMEOUT = float(os.getenv("EXECUTION_TIMEOUT", "120"))
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))


class ExecutorAgent(BaseAgent):
    """
    Universal execution agent that runs commands from Architect's plan.

    Capabilities:
    - Execute any shell command
    - Install dependencies (pip, npm, apt)
    - Run servers in background
    - Stream output in real-time
    - Capture preview URLs for web apps
    """

    name = "executor"
    system_prompt = "You are a code executor."  # Not used for LLM calls

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """Execute all steps from the Architect's execution plan."""
        
        if not state.execution_plan or not state.execution_plan.steps:
            # Fallback: try to run main.py if it exists
            return await self._fallback_execution(state)
        
        all_output = []
        overall_success = True
        
        for i, step in enumerate(state.execution_plan.steps):
            step_label = step.label or step.cmd
            logger.info(f"[{self.name}] Step {i+1}: {step_label}")
            
            # Emit step start event
            await broadcaster.emit(
                "execution_step",
                self.name,
                {"step": i + 1, "label": step_label, "cmd": step.cmd, "status": "running"}
            )
            
            if step.background:
                # Start background process (for servers)
                success, output, port = await self._run_background(step.cmd, step.port)
                if port:
                    state.preview_url = f"http://localhost:{port}"
            else:
                # Run foreground command
                success, output = await self._run_command(step.cmd)
            
            all_output.append(f"=== {step_label} ===\n{output}")
            
            # Emit step result
            await broadcaster.emit(
                "execution_step",
                self.name,
                {"step": i + 1, "label": step_label, "status": "success" if success else "failed", "output": output[:500]}
            )
            
            if not success:
                overall_success = False
                logger.error(f"[{self.name}] Step failed: {step_label}")
                break
        
        # Combine all output
        full_output = "\n\n".join(all_output)
        
        # Set preview URL if specified
        if state.execution_plan.preview_url:
            state.preview_url = state.execution_plan.preview_url
        
        # Update state
        state.execution_output = full_output
        state.execution_success = overall_success
        state.add_history(
            self.name,
            "execute",
            f"Ran {len(state.execution_plan.steps)} steps, success={overall_success}"
        )
        
        # Emit final execution result
        await broadcaster.emit_execution(
            self.name,
            overall_success,
            full_output[:1000],
            0 if overall_success else 1
        )
        
        logger.info(f"[{self.name}] Execution {'succeeded' if overall_success else 'failed'}")
        
        return state

    async def _run_command(self, cmd: str) -> tuple[bool, str]:
        """Run a command and capture output."""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=EXECUTION_TIMEOUT,
                cwd=str(WORKSPACE_DIR),
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n--- STDERR ---\n" + result.stderr
            
            return result.returncode == 0, output.strip()
            
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {EXECUTION_TIMEOUT}s"
        except Exception as e:
            logger.exception(f"[{self.name}] Command error: {e}")
            return False, f"Error: {e}"

    async def _run_background(self, cmd: str, port: int | None) -> tuple[bool, str, int | None]:
        """Start a background process (for servers)."""
        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(WORKSPACE_DIR),
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            
            # Wait briefly to check if it started successfully
            await asyncio.sleep(2)
            
            if process.poll() is not None:
                # Process died immediately
                stdout, stderr = process.communicate()
                output = stdout.decode() + "\n" + stderr.decode()
                return False, f"Process exited immediately:\n{output}", None
            
            return True, f"Started background process (PID: {process.pid})", port
            
        except Exception as e:
            logger.exception(f"[{self.name}] Background process error: {e}")
            return False, f"Error: {e}", None

    async def _fallback_execution(self, state: OrchestratorState) -> OrchestratorState:
        """Fallback: try to run main.py or the first Python file."""
        
        main_py = WORKSPACE_DIR / "main.py"
        if main_py.exists():
            cmd = f"python {main_py}"
        elif state.file_path:
            cmd = f"python {state.file_path}"
        else:
            # Find any .py file
            py_files = list(WORKSPACE_DIR.glob("*.py"))
            if py_files:
                cmd = f"python {py_files[0]}"
            else:
                state.execution_output = "No executable files found"
                state.execution_success = False
                return state
        
        success, output = await self._run_command(cmd)
        
        state.execution_output = output
        state.execution_success = success
        state.add_history(self.name, "execute", f"Fallback execution: {cmd}")
        
        await broadcaster.emit_execution(self.name, success, output[:1000], 0 if success else 1)
        
        return state
