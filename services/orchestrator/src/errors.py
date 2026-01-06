"""
Error Classification and Recovery System

Provides error classification and recovery strategies for the orchestration pipeline.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors that can occur during orchestration."""

    # Syntax errors in generated code
    SYNTAX = "syntax"

    # Runtime errors during code execution
    RUNTIME = "runtime"

    # Logic errors (code runs but produces wrong output)
    LOGIC = "logic"

    # JSON parsing errors from LLM responses
    PARSE = "parse"

    # Network/connection errors to inference service
    CONNECTION = "connection"

    # Timeout errors
    TIMEOUT = "timeout"

    # Unknown/uncategorized errors
    UNKNOWN = "unknown"


class RecoveryStrategy(Enum):
    """Strategies for recovering from errors."""

    # Retry with the same prompt
    RETRY = "retry"

    # Retry with a "fix this error" prompt
    FIX = "fix"

    # Retry with a format correction prompt
    REFORMAT = "reformat"

    # Skip this agent and continue
    SKIP = "skip"

    # Abort the entire operation
    ABORT = "abort"

    # Reconnect and retry
    RECONNECT = "reconnect"


@dataclass
class ClassifiedError:
    """A classified error with recovery strategy."""

    category: ErrorCategory
    message: str
    original_exception: Exception | None
    recovery_strategy: RecoveryStrategy
    context: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"


class ErrorClassifier:
    """Classifies errors and determines recovery strategies."""

    # Patterns for identifying error types
    SYNTAX_PATTERNS = [
        r"SyntaxError:",
        r"IndentationError:",
        r"TabError:",
        r"invalid syntax",
        r"unexpected EOF",
        r"expected ':'",
    ]

    RUNTIME_PATTERNS = [
        r"NameError:",
        r"TypeError:",
        r"ValueError:",
        r"AttributeError:",
        r"KeyError:",
        r"IndexError:",
        r"ZeroDivisionError:",
        r"ImportError:",
        r"ModuleNotFoundError:",
        r"FileNotFoundError:",
        r"PermissionError:",
        r"RuntimeError:",
    ]

    CONNECTION_PATTERNS = [
        r"ConnectionError:",
        r"ConnectionRefusedError:",
        r"ConnectionResetError:",
        r"BrokenPipeError:",
        r"httpx\.ConnectError",
        r"httpx\.ReadTimeout",
        r"ECONNREFUSED",
        r"Connection refused",
        r"Network is unreachable",
    ]

    TIMEOUT_PATTERNS = [
        r"TimeoutError:",
        r"asyncio\.TimeoutError",
        r"httpx\.TimeoutException",
        r"ReadTimeout",
        r"ConnectTimeout",
        r"timed out",
    ]

    PARSE_PATTERNS = [
        r"JSONDecodeError:",
        r"json\.decoder\.JSONDecodeError",
        r"Expecting value:",
        r"Invalid JSON",
        r"Unterminated string",
        r"Extra data:",
    ]

    def classify(self, error: Exception | str, context: dict | None = None) -> ClassifiedError:
        """
        Classify an error and determine the appropriate recovery strategy.

        Args:
            error: The exception or error message to classify
            context: Optional context about where the error occurred

        Returns:
            ClassifiedError with category and recovery strategy
        """
        error_str = str(error)

        # Check patterns in order of specificity
        if self._matches_any(error_str, self.PARSE_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.PARSE,
                message=error_str,
                original_exception=error if isinstance(error, Exception) else None,
                recovery_strategy=RecoveryStrategy.REFORMAT,
                context=context,
            )

        if self._matches_any(error_str, self.TIMEOUT_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.TIMEOUT,
                message=error_str,
                original_exception=error if isinstance(error, Exception) else None,
                recovery_strategy=RecoveryStrategy.RETRY,
                context=context,
            )

        if self._matches_any(error_str, self.CONNECTION_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.CONNECTION,
                message=error_str,
                original_exception=error if isinstance(error, Exception) else None,
                recovery_strategy=RecoveryStrategy.RECONNECT,
                context=context,
            )

        if self._matches_any(error_str, self.SYNTAX_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.SYNTAX,
                message=error_str,
                original_exception=error if isinstance(error, Exception) else None,
                recovery_strategy=RecoveryStrategy.FIX,
                context=context,
            )

        if self._matches_any(error_str, self.RUNTIME_PATTERNS):
            return ClassifiedError(
                category=ErrorCategory.RUNTIME,
                message=error_str,
                original_exception=error if isinstance(error, Exception) else None,
                recovery_strategy=RecoveryStrategy.FIX,
                context=context,
            )

        # Default to unknown
        return ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            message=error_str,
            original_exception=error if isinstance(error, Exception) else None,
            recovery_strategy=RecoveryStrategy.ABORT,
            context=context,
        )

    def _matches_any(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False


# Format fix prompts for different error categories
FORMAT_FIX_PROMPTS = {
    ErrorCategory.PARSE: """Your previous response could not be parsed as valid JSON.
Please respond with ONLY valid JSON, no additional text or explanation.
Make sure to:
- Use double quotes for strings
- No trailing commas
- Properly escape special characters
- Start with {{ and end with }}""",
    ErrorCategory.SYNTAX: """The code you generated has a syntax error:
{error}

Please fix the syntax error and provide the corrected code.""",
    ErrorCategory.RUNTIME: """The code you generated produced a runtime error:
{error}

Please fix the error and provide the corrected code.""",
}


def get_fix_prompt(error: ClassifiedError) -> str:
    """Get a fix prompt for the given error."""
    template = FORMAT_FIX_PROMPTS.get(
        error.category,
        "An error occurred: {error}\n\nPlease try again.",
    )
    return template.format(error=error.message)


class RetryPolicy:
    """Policy for retrying operations with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (0-indexed)."""
        delay = self.initial_delay * (self.exponential_base**attempt)
        return min(delay, self.max_delay)

    def should_retry(self, attempt: int, error: ClassifiedError) -> bool:
        """Determine if we should retry given the attempt count and error."""
        if attempt >= self.max_retries:
            return False

        # Don't retry abortable errors
        if error.recovery_strategy == RecoveryStrategy.ABORT:
            return False

        return True


# Default policies
DEFAULT_RETRY_POLICY = RetryPolicy(max_retries=3)
JSON_PARSE_RETRY_POLICY = RetryPolicy(max_retries=2)  # Fewer retries for parse errors
CONNECTION_RETRY_POLICY = RetryPolicy(max_retries=5, initial_delay=2.0)  # More retries for connection
