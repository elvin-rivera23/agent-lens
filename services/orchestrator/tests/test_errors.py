"""Tests for error classification and recovery system."""


from errors import (
    ClassifiedError,
    ErrorCategory,
    ErrorClassifier,
    RecoveryStrategy,
    RetryPolicy,
    get_fix_prompt,
)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""

    def test_all_categories_have_values(self):
        """Test all categories have string values."""
        for category in ErrorCategory:
            assert isinstance(category.value, str)
            assert len(category.value) > 0


class TestErrorClassifier:
    """Tests for ErrorClassifier."""

    def test_classify_syntax_error(self):
        """Test classification of syntax errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("SyntaxError: invalid syntax")
        assert result.category == ErrorCategory.SYNTAX
        assert result.recovery_strategy == RecoveryStrategy.FIX

    def test_classify_indentation_error(self):
        """Test classification of indentation errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("IndentationError: unexpected indent")
        assert result.category == ErrorCategory.SYNTAX
        assert result.recovery_strategy == RecoveryStrategy.FIX

    def test_classify_runtime_error_name_error(self):
        """Test classification of NameError."""
        classifier = ErrorClassifier()

        result = classifier.classify("NameError: name 'foo' is not defined")
        assert result.category == ErrorCategory.RUNTIME
        assert result.recovery_strategy == RecoveryStrategy.FIX

    def test_classify_runtime_error_type_error(self):
        """Test classification of TypeError."""
        classifier = ErrorClassifier()

        result = classifier.classify("TypeError: unsupported operand type(s)")
        assert result.category == ErrorCategory.RUNTIME
        assert result.recovery_strategy == RecoveryStrategy.FIX

    def test_classify_json_parse_error(self):
        """Test classification of JSON parse errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("JSONDecodeError: Expecting value")
        assert result.category == ErrorCategory.PARSE
        assert result.recovery_strategy == RecoveryStrategy.REFORMAT

    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("ConnectionError: Connection refused")
        assert result.category == ErrorCategory.CONNECTION
        assert result.recovery_strategy == RecoveryStrategy.RECONNECT

    def test_classify_timeout_error(self):
        """Test classification of timeout errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("TimeoutError: timed out")
        assert result.category == ErrorCategory.TIMEOUT
        assert result.recovery_strategy == RecoveryStrategy.RETRY

    def test_classify_unknown_error(self):
        """Test classification of unknown errors."""
        classifier = ErrorClassifier()

        result = classifier.classify("SomeWeirdError: something strange happened")
        assert result.category == ErrorCategory.UNKNOWN
        assert result.recovery_strategy == RecoveryStrategy.ABORT

    def test_classify_exception_object(self):
        """Test classification with actual exception object."""
        classifier = ErrorClassifier()

        exc = ValueError("some value error")
        result = classifier.classify(exc)

        assert result.original_exception is exc

    def test_classify_with_context(self):
        """Test classification with context."""
        classifier = ErrorClassifier()

        context = {"agent": "coder", "step": 3}
        result = classifier.classify("SyntaxError: invalid", context=context)

        assert result.context == context


class TestClassifiedError:
    """Tests for ClassifiedError dataclass."""

    def test_str_representation(self):
        """Test string representation of ClassifiedError."""
        error = ClassifiedError(
            category=ErrorCategory.SYNTAX,
            message="SyntaxError: invalid syntax at line 5",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.FIX,
        )

        str_repr = str(error)
        assert "[syntax]" in str_repr
        assert "invalid syntax" in str_repr


class TestGetFixPrompt:
    """Tests for get_fix_prompt function."""

    def test_parse_error_fix_prompt(self):
        """Test fix prompt for parse errors."""
        error = ClassifiedError(
            category=ErrorCategory.PARSE,
            message="JSON parse failed",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.REFORMAT,
        )

        prompt = get_fix_prompt(error)
        assert "JSON" in prompt
        assert "double quotes" in prompt.lower() or "valid" in prompt.lower()

    def test_syntax_error_fix_prompt(self):
        """Test fix prompt for syntax errors."""
        error = ClassifiedError(
            category=ErrorCategory.SYNTAX,
            message="SyntaxError: invalid syntax",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.FIX,
        )

        prompt = get_fix_prompt(error)
        assert "syntax" in prompt.lower()
        assert "SyntaxError" in prompt

    def test_runtime_error_fix_prompt(self):
        """Test fix prompt for runtime errors."""
        error = ClassifiedError(
            category=ErrorCategory.RUNTIME,
            message="NameError: undefined variable",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.FIX,
        )

        prompt = get_fix_prompt(error)
        assert "runtime" in prompt.lower() or "error" in prompt.lower()


class TestRetryPolicy:
    """Tests for RetryPolicy."""

    def test_default_values(self):
        """Test default retry policy values."""
        policy = RetryPolicy()

        assert policy.max_retries == 3
        assert policy.initial_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 2.0

    def test_get_delay_first_attempt(self):
        """Test delay calculation for first attempt."""
        policy = RetryPolicy(initial_delay=1.0, exponential_base=2.0)

        delay = policy.get_delay(0)
        assert delay == 1.0

    def test_get_delay_exponential_growth(self):
        """Test delay increases exponentially."""
        policy = RetryPolicy(initial_delay=1.0, exponential_base=2.0)

        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(3) == 8.0

    def test_get_delay_capped_at_max(self):
        """Test delay is capped at max_delay."""
        policy = RetryPolicy(initial_delay=1.0, max_delay=5.0, exponential_base=2.0)

        # At attempt 3, delay would be 8.0, but should be capped at 5.0
        assert policy.get_delay(3) == 5.0
        assert policy.get_delay(10) == 5.0

    def test_should_retry_within_limit(self):
        """Test should_retry returns True within limit."""
        policy = RetryPolicy(max_retries=3)
        error = ClassifiedError(
            category=ErrorCategory.CONNECTION,
            message="connection failed",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.RECONNECT,
        )

        assert policy.should_retry(0, error) is True
        assert policy.should_retry(1, error) is True
        assert policy.should_retry(2, error) is True

    def test_should_retry_at_limit(self):
        """Test should_retry returns False at limit."""
        policy = RetryPolicy(max_retries=3)
        error = ClassifiedError(
            category=ErrorCategory.CONNECTION,
            message="connection failed",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.RECONNECT,
        )

        assert policy.should_retry(3, error) is False
        assert policy.should_retry(4, error) is False

    def test_should_retry_abort_strategy(self):
        """Test should_retry returns False for abort strategy."""
        policy = RetryPolicy(max_retries=3)
        error = ClassifiedError(
            category=ErrorCategory.UNKNOWN,
            message="unknown error",
            original_exception=None,
            recovery_strategy=RecoveryStrategy.ABORT,
        )

        assert policy.should_retry(0, error) is False
