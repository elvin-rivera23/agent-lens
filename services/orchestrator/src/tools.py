"""
Tool System for AgentLens Orchestrator

Provides tools that agents can use to interact with the workspace:
- GrepTool: Search files using regex patterns
- FileReadTool: Read file contents with optional line ranges
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Workspace directory for sandboxed operations
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    output: str
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for tools."""

    name: str = "base"
    description: str = "Base tool"

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        raise NotImplementedError

    def to_schema(self) -> dict:
        """Return OpenAI-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._get_parameters(),
            },
        }

    @abstractmethod
    def _get_parameters(self) -> dict:
        """Return JSON schema for tool parameters."""
        raise NotImplementedError


class GrepTool(BaseTool):
    """Search files in workspace using regex patterns."""

    name = "grep"
    description = (
        "Search for a pattern in files within the workspace. "
        "Returns matching lines with file paths and line numbers. "
        "Use this to find code, functions, or specific text patterns."
    )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., '*.py')",
                    "default": "*",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 20,
                },
            },
            "required": ["pattern"],
        }

    def execute(
        self,
        pattern: str,
        file_pattern: str = "*",
        max_results: int = 20,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute grep search in workspace."""
        if not WORKSPACE_DIR.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"Workspace directory does not exist: {WORKSPACE_DIR}",
            )

        try:
            # Use grep if available, otherwise fall back to Python
            results = self._python_grep(pattern, file_pattern, max_results)
            return ToolResult(success=True, output=results)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _python_grep(
        self, pattern: str, file_pattern: str, max_results: int
    ) -> str:
        """Pure Python implementation of grep."""
        regex = re.compile(pattern, re.IGNORECASE)
        matches: list[str] = []

        for filepath in WORKSPACE_DIR.rglob(file_pattern):
            if filepath.is_file() and not self._should_skip(filepath):
                try:
                    with open(filepath, encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                rel_path = filepath.relative_to(WORKSPACE_DIR)
                                matches.append(f"{rel_path}:{i}: {line.rstrip()}")
                                if len(matches) >= max_results:
                                    break
                except (OSError, UnicodeDecodeError):
                    continue

            if len(matches) >= max_results:
                break

        if not matches:
            return f"No matches found for pattern: {pattern}"

        header = f"Found {len(matches)} matches:\n"
        return header + "\n".join(matches)

    def _should_skip(self, filepath: Path) -> bool:
        """Check if file should be skipped (binary, cache, etc.)."""
        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        skip_exts = {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".jpg", ".png"}

        for part in filepath.parts:
            if part in skip_dirs:
                return True

        return filepath.suffix.lower() in skip_exts


class FileReadTool(BaseTool):
    """Read file contents from workspace."""

    name = "read_file"
    description = (
        "Read the contents of a file in the workspace. "
        "Can optionally read only specific line ranges. "
        "Use this to examine code or configuration files."
    )

    def _get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to file relative to workspace root",
                },
                "start_line": {
                    "type": "integer",
                    "description": "First line to read (1-indexed, inclusive)",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Last line to read (1-indexed, inclusive). -1 for end of file.",
                    "default": -1,
                },
            },
            "required": ["path"],
        }

    def execute(
        self,
        path: str,
        start_line: int = 1,
        end_line: int = -1,
        **kwargs: Any,
    ) -> ToolResult:
        """Read file contents."""
        # Normalize and validate path
        try:
            filepath = (WORKSPACE_DIR / path).resolve()

            # Security check: ensure path is within workspace
            if not str(filepath).startswith(str(WORKSPACE_DIR.resolve())):
                return ToolResult(
                    success=False,
                    output="",
                    error="Access denied: path outside workspace",
                )

            if not filepath.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}",
                )

            if not filepath.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a file: {path}",
                )

            # Read file
            with open(filepath, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Handle line range
            start_idx = max(0, start_line - 1)
            end_idx = total_lines if end_line == -1 else min(end_line, total_lines)

            selected_lines = lines[start_idx:end_idx]

            # Format output with line numbers
            output_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                output_lines.append(f"{i:4d} | {line.rstrip()}")

            header = f"File: {path} (lines {start_idx + 1}-{end_idx} of {total_lines})\n"
            return ToolResult(success=True, output=header + "\n".join(output_lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ToolRegistry:
    """Registry of available tools for agents."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        """Get OpenAI function schemas for all tools."""
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name."""
        tool = self.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}",
            )
        return tool.execute(**kwargs)


# Default registry with standard tools
def create_default_registry() -> ToolRegistry:
    """Create a registry with default tools."""
    registry = ToolRegistry()
    registry.register(GrepTool())
    registry.register(FileReadTool())
    return registry
