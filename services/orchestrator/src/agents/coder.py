"""
Coder Agent

Generates files based on Architect's plan. Iterates through planned_files,
generating each one and emitting FILE_CREATED events.
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
    Agent that generates code for each file in the Architect's plan.

    Responsibilities:
    - Iterate through planned_files from state
    - Generate appropriate content for each file
    - Write files to workspace
    - Emit FILE_CREATED events for dashboard updates
    """

    name = "coder"
    system_prompt = """You are an expert code generator. Generate the content for ONE specific file.

Given:
- The overall project task
- The specific file you're generating (path and description)
- Other files in the project (for context on imports/dependencies)

Output ONLY the file content with appropriate code fences.

## Rules
- Generate ONLY the content for the specified file
- Use proper imports from other project files when needed
- Include appropriate comments and docstrings
- For requirements.txt: list only the packages needed
- For config files: use proper format (JSON, YAML, etc.)

## Output Format
```python
# Your code here (or appropriate language for the file type)
```

For non-Python files, use the appropriate fence:
- ```txt for requirements.txt
- ```json for JSON files
- ```hcl for Terraform
- ```javascript for JS/Node"""

    def __init__(self):
        super().__init__()

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """Generate all files from the Architect's plan."""

        # Ensure workspace exists
        WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

        if not state.planned_files:
            # Fallback to old behavior if no planned files
            return await self._generate_single_file(state)

        # Generate each file in the plan
        all_files_context = [f"{f.path}: {f.description}" for f in state.planned_files]

        for i, file_spec in enumerate(state.planned_files):
            if file_spec.generated:
                continue  # Skip already generated files

            logger.info(f"[{self.name}] Generating file {i+1}/{len(state.planned_files)}: {file_spec.path}")

            # Build prompt for this specific file
            messages = self._build_file_prompt(state, file_spec, all_files_context)

            # Determine file path
            file_path = WORKSPACE_DIR / file_spec.path
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Generate with streaming
            response = await self.call_llm_streaming(
                messages,
                max_tokens=2048,
                file_path=str(file_path)
            )

            # Extract content from response
            content = self._extract_content(response, file_spec.path)

            if not content:
                logger.warning(f"[{self.name}] Failed to extract content for {file_spec.path}")
                content = f"# TODO: Generate content for {file_spec.path}\n"

            # Write file
            file_path.write_text(content, encoding="utf-8")

            # Update file spec
            file_spec.content = content
            file_spec.generated = True

            # Add to workspace files
            state.add_file(str(file_path), content)

            # Emit event for dashboard
            await broadcaster.emit_file_created(self.name, file_spec.path, content)

            logger.info(f"[{self.name}] Wrote {len(content)} chars to {file_path}")

        # Update state with last file for compatibility
        if state.planned_files:
            last_file = state.planned_files[-1]
            state.code = last_file.content
            state.file_path = str(WORKSPACE_DIR / last_file.path)

        state.add_history(
            self.name,
            "generate",
            f"Generated {len(state.planned_files)} files"
        )

        return state

    def _build_file_prompt(
        self,
        state: OrchestratorState,
        file_spec,
        all_files: list[str]
    ) -> list[dict]:
        """Build prompt for generating a specific file."""

        other_files = "\n".join(f"- {f}" for f in all_files if f != f"{file_spec.path}: {file_spec.description}")

        # Include already generated file contents for imports
        existing_content = ""
        for f in state.planned_files:
            if f.generated and f.path != file_spec.path:
                existing_content += f"\n\n### {f.path}\n```\n{f.content[:500]}...\n```"

        prompt = f"""Generate the content for this file:

**Project Task:** {state.task}

**File to Generate:** {file_spec.path}
**Description:** {file_spec.description}

**Other Project Files:**
{other_files}
{existing_content if existing_content else ""}

Generate ONLY the content for {file_spec.path}. Output the complete file content in a code block."""

        return [{"role": "user", "content": prompt}]

    def _extract_content(self, response: str, file_path: str) -> str | None:
        """Extract file content from LLM response."""

        # Determine expected language from file extension
        ext = Path(file_path).suffix.lower()
        lang_map = {
            ".py": ["python", "py"],
            ".txt": ["txt", "text", ""],
            ".json": ["json"],
            ".tf": ["hcl", "terraform"],
            ".js": ["javascript", "js"],
            ".ts": ["typescript", "ts"],
            ".html": ["html"],
            ".css": ["css"],
            ".yaml": ["yaml", "yml"],
            ".yml": ["yaml", "yml"],
            ".md": ["markdown", "md"],
        }

        expected_langs = lang_map.get(ext, [""])

        # Try to find code block with expected language
        for lang in expected_langs:
            pattern = rf"```{lang}\s*(.*?)```"
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            if matches:
                return matches[0].strip()

        # Fallback: any code block
        pattern = r"```\w*\s*(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return matches[0].strip()

        # Last resort: if no code blocks, check if response looks like code
        lines = response.strip().split("\n")
        # Remove lines that look like LLM commentary
        code_lines = [line for line in lines if not line.startswith("Here") and not line.startswith("This")]

        # Only return as code if it looks like actual code (has function def, class, or assignments)
        joined = "\n".join(code_lines)
        if code_lines and any(
            indicator in joined for indicator in ["def ", "class ", "import ", "from ", "=", "print(", "return "]
        ):
            return joined

        return None

    def _extract_code(self, response: str) -> str | None:
        """Extract code from LLM response (wrapper for tests, defaults to Python)."""
        return self._extract_content(response, "generated.py")

    async def _generate_single_file(self, state: OrchestratorState) -> OrchestratorState:
        """Fallback: generate single file (old behavior)."""
        messages = [{"role": "user", "content": f"Write code for: {state.task}"}]

        filename = self._generate_filename(state.task)
        file_path = WORKSPACE_DIR / filename

        response = await self.call_llm_streaming(messages, max_tokens=2048, file_path=str(file_path))
        code = self._extract_content(response, filename) or ""

        file_path.write_text(code, encoding="utf-8")
        await broadcaster.emit_code_written(self.name, str(file_path), code)

        state.code = code
        state.file_path = str(file_path)
        state.add_file(str(file_path), code)

        return state

    def _generate_filename(self, task: str) -> str:
        """Generate filename from task (fallback)."""
        words = task.lower().split()
        stop_words = {"a", "an", "the", "write", "create", "make", "build", "python", "code"}
        meaningful = [w for w in words if w.isalnum() and w not in stop_words][:3]
        name = "_".join(meaningful) if meaningful else "generated"
        name = re.sub(r"[^a-z0-9_]", "", name)
        return f"{name}.py"
