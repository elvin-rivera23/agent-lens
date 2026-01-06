"""
Architect Agent

Decomposes user tasks into structured subtasks using LLM.
This agent runs first in the orchestration pipeline.
"""

import json
import logging
import re

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """
    Agent that analyzes tasks and creates structured execution plans.

    Responsibilities:
    - Understand the user's high-level request
    - Break it down into numbered subtasks
    - Identify dependencies between subtasks
    - Output a structured plan for the Coder agent
    """

    name = "architect"
    system_prompt = """You are an expert software architect and task planner.

Given a coding task, you will:
1. Analyze the requirements
2. Break the task into clear, sequential subtasks
3. Each subtask should be independently codeable

IMPORTANT RULES:
- Output ONLY valid JSON with no extra text
- Use the exact format shown below
- Keep subtasks small and focused (1-3 functions each)
- Order subtasks by dependency (do prerequisites first)

Output format:
{
    "summary": "Brief description of overall approach",
    "subtasks": [
        {
            "id": 1,
            "title": "Short title",
            "description": "What to implement",
            "dependencies": []
        },
        {
            "id": 2,
            "title": "Another task",
            "description": "What to implement",
            "dependencies": [1]
        }
    ]
}

For simple tasks, you can have just 1 subtask.
For complex tasks, break into 2-5 subtasks."""

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Analyze the task and create an execution plan.
        """
        # Build prompt
        messages = [{"role": "user", "content": f"Create an execution plan for this task:\n\n{state.task}"}]

        # Call LLM
        response = await self.call_llm(messages, max_tokens=1024)

        # Parse plan from response
        plan = self._parse_plan(response)

        if not plan:
            # Fallback: create simple single-task plan
            plan = {
                "summary": state.task,
                "subtasks": [
                    {
                        "id": 1,
                        "title": "Complete task",
                        "description": state.task,
                        "dependencies": [],
                    }
                ],
            }
            logger.warning(f"[{self.name}] Failed to parse plan, using fallback")

        # Emit event for Glass-Box visibility
        await broadcaster.emit(
            "plan_created",
            self.name,
            {"subtask_count": len(plan.get("subtasks", []))},
        )

        # Update state
        state.plan = plan
        state.current_subtask = 0
        state.add_history(
            self.name,
            "plan",
            f"Created plan with {len(plan.get('subtasks', []))} subtasks",
        )

        logger.info(f"[{self.name}] Created plan: {plan.get('summary', '')[:100]}")

        return state

    def _parse_plan(self, response: str) -> dict | None:
        """
        Parse the plan JSON from LLM response.

        Handles:
        - Direct JSON response
        - JSON wrapped in ```json code blocks
        - Malformed JSON with recovery attempts
        """
        # Try to find JSON in code block
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            # Find the JSON object in the response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        return None

    def get_current_subtask(self, state: OrchestratorState) -> dict | None:
        """Get the current subtask from the plan."""
        if not state.plan or "subtasks" not in state.plan:
            return None

        subtasks = state.plan["subtasks"]
        if state.current_subtask < len(subtasks):
            return subtasks[state.current_subtask]

        return None
