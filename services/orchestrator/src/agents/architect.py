"""
Architect Agent

Creates multi-file project plans with execution instructions.
Outputs structured JSON for the Coder and Executor agents.
"""

import json
import logging
import re

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState, FileSpec, ExecutionStep, ExecutionPlan
from tools import create_default_registry

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """
    Agent that analyzes tasks and creates multi-file project plans.

    Responsibilities:
    - Understand the user's request
    - Plan a realistic multi-file project structure
    - Define execution steps (build & run commands)
    - Output structured plan for Coder and Executor agents
    """

    name = "architect"
    system_prompt = """You are an expert software architect. Create project plans with MULTIPLE files.

Given a task, output a JSON plan with:
1. **files**: List of files to create (MUST have 2+ files for any real project)
2. **execution**: Steps to build and run the project

## Output Format (STRICT JSON)

```json
{
  "project_name": "my_project",
  "summary": "Brief description of the project",
  "files": [
    {"path": "main.py", "description": "Entry point with CLI/server setup"},
    {"path": "models.py", "description": "Data models and classes"},
    {"path": "utils.py", "description": "Helper functions"},
    {"path": "config.py", "description": "Configuration constants"},
    {"path": "requirements.txt", "description": "Python dependencies"}
  ],
  "execution": {
    "steps": [
      {"cmd": "pip install -r requirements.txt", "label": "Install dependencies"},
      {"cmd": "python main.py", "label": "Run application", "background": false}
    ],
    "preview_type": "terminal",
    "preview_url": ""
  }
}
```

## File Structure Guidelines

- **Static web pages (PREFERRED for visual/simple web)**: index.html, styles.css, script.js - Use this for landing pages, simple apps, UI demos
- **CLI apps**: main.py + separate modules for logic, utils, config
- **Web apps with backend (Flask/FastAPI)**: app.py, routes.py, models.py, templates/, requirements.txt - Only use if database/API is needed
- **Terraform**: main.tf, variables.tf, outputs.tf, providers.tf
- **Node.js**: package.json, index.js, src/ modules

## Execution Guidelines

- **preview_type**: "terminal" for CLI, "iframe" for web servers, "none" for infra
- **background: true** for servers that keep running (Flask, Express, etc.)
- Include install commands (pip install, npm install, etc.)

## Rules
- ALWAYS create multiple files (minimum 2, prefer 3-5)
- Real projects have separation of concerns
- Output ONLY valid JSON, no extra text
- File paths should be relative to project root"""

    def __init__(self):
        super().__init__(tools=create_default_registry())

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """Create a multi-file project plan with execution instructions."""
        messages = [
            {"role": "user", "content": f"Create a multi-file project plan for:\n\n{state.task}"}
        ]

        # Call LLM for plan (streaming for token tracking)
        response = await self.call_llm_streaming(messages, max_tokens=1500)

        # Parse the structured plan
        plan_data = self._parse_plan(response)

        if not plan_data:
            # Fallback: minimal 2-file structure
            plan_data = self._create_fallback_plan(state.task)
            logger.warning(f"[{self.name}] Failed to parse plan, using fallback")

        # Convert to state objects
        planned_files = [
            FileSpec(path=f["path"], description=f.get("description", ""))
            for f in plan_data.get("files", [])
        ]

        exec_data = plan_data.get("execution", {})
        execution_steps = [
            ExecutionStep(
                cmd=s["cmd"],
                label=s.get("label", ""),
                background=s.get("background", False),
                port=s.get("port"),
                requires_approval=s.get("requires_approval", False)
            )
            for s in exec_data.get("steps", [])
        ]

        execution_plan = ExecutionPlan(
            steps=execution_steps,
            preview_type=exec_data.get("preview_type", "terminal"),
            preview_url=exec_data.get("preview_url", "")
        )

        # Build detailed summary for dashboard
        file_desc = " | ".join(f"{f.path}: {f.description[:40]}" for f in planned_files[:3])
        if len(planned_files) > 3:
            file_desc += f" + {len(planned_files) - 3} more"
        summary = plan_data.get("summary", f"Creating: {file_desc}")
        
        # Emit event for dashboard
        await broadcaster.emit(
            "plan_created",
            self.name,
            {
                "file_count": len(planned_files),
                "step_count": len(execution_steps),
                "files": [{"path": f.path, "desc": f.description} for f in planned_files],
                "summary": summary
            },
        )

        # Update state
        state.plan = plan_data
        state.planned_files = planned_files
        state.execution_plan = execution_plan
        state.current_file_index = 0
        state.add_history(
            self.name,
            "plan",
            f"Created plan: {len(planned_files)} files, {len(execution_steps)} exec steps",
        )

        logger.info(f"[{self.name}] Plan: {len(planned_files)} files, {len(execution_steps)} steps")

        return state

    def _parse_plan(self, response: str) -> dict | None:
        """Parse the plan JSON from LLM response."""
        # Try JSON in code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if "files" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end])
                if "files" in parsed:
                    return parsed
        except json.JSONDecodeError:
            pass

        return None

    def _create_fallback_plan(self, task: str) -> dict:
        """Create a minimal fallback plan."""
        return {
            "project_name": "project",
            "summary": task,
            "files": [
                {"path": "main.py", "description": "Main application entry point"},
                {"path": "utils.py", "description": "Helper functions and utilities"}
            ],
            "execution": {
                "steps": [
                    {"cmd": "python main.py", "label": "Run application"}
                ],
                "preview_type": "terminal",
                "preview_url": ""
            }
        }
