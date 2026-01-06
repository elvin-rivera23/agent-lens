"""Tests for the tool system."""

import tempfile
from pathlib import Path

import pytest

from tools import (
    BaseTool,
    FileReadTool,
    GrepTool,
    ToolRegistry,
    ToolResult,
    create_default_registry,
)


class TestGrepTool:
    """Tests for GrepTool."""

    def test_search_pattern_found(self, tmp_path: Path):
        """Test grep finds matching patterns."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello_world():\n    print('Hello!')\n")

        # Patch WORKSPACE_DIR
        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = GrepTool()
            result = tool.execute(pattern="def hello")

            assert result.success is True
            assert "hello_world" in result.output
            assert "test.py" in result.output
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_search_pattern_not_found(self, tmp_path: Path):
        """Test grep handles no matches gracefully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass\n")

        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = GrepTool()
            result = tool.execute(pattern="nonexistent_pattern")

            assert result.success is True
            assert "No matches found" in result.output
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_invalid_regex(self, tmp_path: Path):
        """Test grep handles invalid regex."""
        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = GrepTool()
            result = tool.execute(pattern="[invalid(regex")

            assert result.success is False
            assert "Invalid regex" in result.error
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_file_pattern_filter(self, tmp_path: Path):
        """Test grep respects file pattern filter."""
        # Create Python and JS files
        py_file = tmp_path / "code.py"
        py_file.write_text("def target(): pass\n")

        js_file = tmp_path / "code.js"
        js_file.write_text("function target() {}\n")

        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = GrepTool()
            result = tool.execute(pattern="target", file_pattern="*.py")

            assert result.success is True
            assert "code.py" in result.output
            assert "code.js" not in result.output
        finally:
            tools.WORKSPACE_DIR = original_workspace


class TestFileReadTool:
    """Tests for FileReadTool."""

    def test_read_entire_file(self, tmp_path: Path):
        """Test reading entire file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = FileReadTool()
            result = tool.execute(path="test.txt")

            assert result.success is True
            assert "Line 1" in result.output
            assert "Line 2" in result.output
            assert "Line 3" in result.output
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_read_line_range(self, tmp_path: Path):
        """Test reading specific line range."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = FileReadTool()
            result = tool.execute(path="test.txt", start_line=2, end_line=4)

            assert result.success is True
            assert "Line 2" in result.output
            assert "Line 3" in result.output
            assert "Line 4" in result.output
            # Line 1 and 5 should not be in output
            lines = result.output.split("\n")
            content_lines = [l for l in lines if "|" in l]
            assert len(content_lines) == 3
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_file_not_found(self, tmp_path: Path):
        """Test handling of missing file."""
        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = FileReadTool()
            result = tool.execute(path="nonexistent.txt")

            assert result.success is False
            assert "not found" in result.error.lower()
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_path_traversal_blocked(self, tmp_path: Path):
        """Test that path traversal attacks are blocked."""
        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            tool = FileReadTool()
            result = tool.execute(path="../../../etc/passwd")

            assert result.success is False
            assert "denied" in result.error.lower() or "not found" in result.error.lower()
        finally:
            tools.WORKSPACE_DIR = original_workspace


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_and_get(self):
        """Test tool registration and retrieval."""
        registry = ToolRegistry()
        tool = GrepTool()

        registry.register(tool)
        retrieved = registry.get("grep")

        assert retrieved is tool

    def test_get_unknown_tool(self):
        """Test getting unknown tool returns None."""
        registry = ToolRegistry()

        assert registry.get("unknown") is None

    def test_execute_registered_tool(self, tmp_path: Path):
        """Test executing tool through registry."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def foo(): pass\n")

        import tools
        original_workspace = tools.WORKSPACE_DIR
        tools.WORKSPACE_DIR = tmp_path

        try:
            registry = create_default_registry()
            result = registry.execute("grep", pattern="def foo")

            assert result.success is True
        finally:
            tools.WORKSPACE_DIR = original_workspace

    def test_execute_unknown_tool(self):
        """Test executing unknown tool returns error."""
        registry = ToolRegistry()
        result = registry.execute("unknown")

        assert result.success is False
        assert "Unknown tool" in result.error

    def test_get_schemas(self):
        """Test getting OpenAI function schemas."""
        registry = create_default_registry()
        schemas = registry.get_schemas()

        assert len(schemas) == 2
        tool_names = [s["function"]["name"] for s in schemas]
        assert "grep" in tool_names
        assert "read_file" in tool_names


class TestDefaultRegistry:
    """Tests for default registry creation."""

    def test_has_grep_tool(self):
        """Test default registry has grep tool."""
        registry = create_default_registry()
        assert registry.get("grep") is not None

    def test_has_file_read_tool(self):
        """Test default registry has file read tool."""
        registry = create_default_registry()
        assert registry.get("read_file") is not None
