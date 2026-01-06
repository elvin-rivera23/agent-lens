"""
Architect Agent

Decomposes user tasks into structured subtasks using LLM.
This agent runs first in the orchestration pipeline.
Can use tools to search and read files in the workspace.
"""

import json
import logging
import re

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState
from tools import create_default_registry

logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """
    Agent that analyzes tasks and creates structured execution plans.

    Responsibilities:
    - Understand the user's high-level request
    - Use tools to search and examine existing code
    - Break it down into numbered subtasks
    - Identify dependencies between subtasks
    - Output a structured plan for the Coder agent
    """

    name = "architect"
    system_prompt = """You are an expert software architect and task planner.

Given a coding task, you will:
1. Analyze the requirements
2. Optionally use tools to search/read existing code
3. Break the task into clear, sequential subtasks

## Available Tools

You can use tools by outputting a JSON block:
```json
{"tool": "grep", "args": {"pattern": "def function_name", "file_pattern": "*.py"}}
```

**grep** - Search files for patterns
- pattern: Regex pattern to search for
- file_pattern: Optional glob (e.g., "*.py")
- max_results: Max results (default 20)

**read_file** - Read file contents
- path: Path relative to workspace
- start_line: First line (1-indexed)
- end_line: Last line (-1 for end)

After tool results, continue planning.

## Output Format

When ready to output your plan, use this EXACT JSON format:
```json
{
    "summary": "Brief description of overall approach",
    "subtasks": [
        {
            "id": 1,
            "title": "Short title",
            "description": "What to implement",
            "dependencies": []
        }
    ]
}
```

IMPORTANT RULES:
- Output ONLY valid JSON with no extra text when giving final plan
- Keep subtasks small and focused (1-3 functions each)
- Order subtasks by dependency (do prerequisites first)
- For simple tasks, you can have just 1 subtask
- For complex tasks, break into 2-5 subtasks"""

    def __init__(self):
        # Initialize with default tool registry
        super().__init__(tools=create_default_registry())

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Analyze the task and create an execution plan.
        May use tools to explore existing code first.
        """
        # Build initial prompt
        messages = [
            {"role": "user", "content": f"Create an execution plan for this task:\n\n{state.task}"}
        ]

        # Allow up to 3 tool use iterations
        max_tool_iterations = 3
        tool_context = []

        for _iteration in range(max_tool_iterations):
            # Call LLM
            response = await self.call_llm(messages, max_tokens=1024)

            # Check for tool calls
            tool_calls = self.parse_tool_calls(response)

            if not tool_calls:
                # No more tool calls, parse the plan
                break

            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["tool"]
                tool_args = tool_call["args"]

                result = self.execute_tool(tool_name, **tool_args)

                tool_output = result.output if result.success else f"Error: {result.error}"
                tool_context.append(f"Tool: {tool_name}\nResult:\n{tool_output}")

                # Emit event for Glass-Box visibility
                await broadcaster.emit(
                    "tool_executed",
                    self.name,
                    {"tool": tool_name, "success": result.success},
                )

            # Add tool results to conversation
            messages.append({"role": "assistant", "content": response})
            messages.append({
                "role": "user",
                "content": "Tool results:\n\n" + "\n\n---\n\n".join(tool_context) +
                           "\n\nNow continue with your analysis and output the final plan."
            })
            tool_context = []

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
                parsed = json.loads(json_match.group(1))
                # Validate it's a plan (has subtasks)
                if "subtasks" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            # Find the JSON object in the response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(response[start:end])
                if "subtasks" in parsed:
                    return parsed
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

