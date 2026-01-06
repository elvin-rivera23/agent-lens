"""
Reviewer Agent

Performs code quality checks before execution.
This agent runs after Coder and before Executor.
"""

import ast
import logging
import re

from agents.base import BaseAgent
from events import broadcaster
from state import OrchestratorState

logger = logging.getLogger(__name__)

# Security: Dangerous patterns to detect
DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "eval() is dangerous"),
    (r"\bexec\s*\(", "exec() is dangerous"),
    (r"\b__import__\s*\(", "__import__() is dangerous"),
    (r"\bos\.system\s*\(", "os.system() is dangerous"),
    (r"\bsubprocess\.call\s*\(.*shell\s*=\s*True", "shell=True is dangerous"),
    (r"\bopen\s*\([^)]*,\s*['\"]w['\"]", "Writing files may be dangerous"),
]

# Imports that are always allowed
SAFE_IMPORTS = {
    "math",
    "random",
    "datetime",
    "json",
    "re",
    "collections",
    "itertools",
    "functools",
    "typing",
    "dataclasses",
    "enum",
    "pathlib",
    "string",
    "textwrap",
}


class ReviewerAgent(BaseAgent):
    """
    Agent that reviews generated code before execution.

    Responsibilities:
    - Syntax validation (AST parsing)
    - Security checks (dangerous patterns)
    - Basic style checks
    - Provide feedback for fixes

    Does NOT call LLM - uses static analysis for speed.
    """

    name = "reviewer"
    system_prompt = "You are a code reviewer."  # Not used

    async def invoke(self, state: OrchestratorState) -> OrchestratorState:
        """
        Review the generated code and update state with results.
        """
        code = state.code

        if not code:
            state.review_passed = False
            state.review_feedback = "No code to review"
            state.add_history(self.name, "review", "No code to review")
            return state

        issues = []

        # 1. Syntax check
        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            issues.append(f"Syntax error: {syntax_error}")

        # 2. Security check
        security_issues = self._check_security(code)
        issues.extend(security_issues)

        # 3. Basic quality checks
        quality_issues = self._check_quality(code)
        issues.extend(quality_issues)

        # Determine pass/fail
        passed = len(issues) == 0

        # Update state
        state.review_passed = passed
        state.review_feedback = "\n".join(issues) if issues else "All checks passed"
        state.review_attempts += 1

        # Emit event for Glass-Box visibility
        await broadcaster.emit(
            "code_reviewed",
            self.name,
            {
                "passed": passed,
                "issue_count": len(issues),
                "attempt": state.review_attempts,
            },
        )

        status = "passed" if passed else f"failed with {len(issues)} issues"
        state.add_history(self.name, "review", status)
        logger.info(f"[{self.name}] Review {status}")

        return state

    def _check_syntax(self, code: str) -> tuple[bool, str]:
        """
        Check if code has valid Python syntax.

        Returns:
            (is_valid, error_message)
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    def _check_security(self, code: str) -> list[str]:
        """
        Check for dangerous patterns in code.

        Returns list of security issues found.
        """
        issues = []

        for pattern, message in DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                issues.append(f"Security: {message}")

        return issues

    def _check_quality(self, code: str) -> list[str]:
        """
        Basic code quality checks.

        Returns list of quality issues.
        """
        issues = []

        # Check for very long lines (>120 chars)
        lines = code.split("\n")
        long_lines = [i + 1 for i, line in enumerate(lines) if len(line) > 120]
        if long_lines:
            issues.append(f"Quality: Lines too long (>120 chars): {long_lines[:3]}")

        # Check for missing docstrings on functions
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not ast.get_docstring(node):
                        # Only warn, don't fail
                        pass
        except SyntaxError:
            pass  # Already caught in syntax check

        return issues

    def can_retry_review(self, state: OrchestratorState) -> bool:
        """Check if we can retry after a failed review."""
        return state.review_attempts < state.max_review_attempts
