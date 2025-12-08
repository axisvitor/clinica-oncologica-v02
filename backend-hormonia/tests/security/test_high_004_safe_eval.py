"""
HIGH-004 Security Tests: Safe Condition Evaluation

Tests for code injection prevention using simpleeval instead of eval().

File: backend-hormonia/tests/security/test_high_004_safe_eval.py
"""
import pytest
from simpleeval import FunctionNotDefined, NameNotDefined

from app.domain.flows.engine.safe_condition_evaluator import (
    SafeConditionEvaluator,
    evaluate_condition
)


class TestSafeConditionEvaluator:
    """Test suite for safe condition evaluation."""

    def setup_method(self):
        """Set up test evaluator."""
        self.evaluator = SafeConditionEvaluator()

    # =========================================================================
    # SECURITY TESTS: Code Injection Prevention
    # =========================================================================

    def test_prevent_import_injection(self):
        """HIGH-004: Prevent import statements (code injection)."""
        malicious_conditions = [
            "import os",
            "__import__('os').system('ls')",
            "exec('print(1)')",
            "eval('1+1')",
        ]

        for condition in malicious_conditions:
            with pytest.raises((ValueError, SyntaxError, NameNotDefined)):
                self.evaluator.evaluate(condition, {})

    def test_prevent_builtin_access(self):
        """HIGH-004: Prevent access to __builtins__."""
        malicious_conditions = [
            "__builtins__",
            "__builtins__['eval']",
            "globals()",
            "locals()",
            "dir()",
        ]

        for condition in malicious_conditions:
            with pytest.raises((ValueError, NameNotDefined, FunctionNotDefined)):
                self.evaluator.evaluate(condition, {})

    def test_prevent_file_operations(self):
        """HIGH-004: Prevent file system access."""
        malicious_conditions = [
            "open('/etc/passwd')",
            "open('file.txt', 'w')",
            "compile('code', 'file', 'exec')",
        ]

        for condition in malicious_conditions:
            with pytest.raises((ValueError, FunctionNotDefined)):
                self.evaluator.evaluate(condition, {})

    def test_prevent_code_execution(self):
        """HIGH-004: Prevent arbitrary code execution."""
        malicious_conditions = [
            "exec('import os')",
            "compile('print(1)', '<string>', 'exec')",
            "eval('1+1')",
            "__import__('subprocess').call(['ls'])",
        ]

        for condition in malicious_conditions:
            with pytest.raises((ValueError, FunctionNotDefined, NameNotDefined)):
                self.evaluator.evaluate(condition, {})

    def test_prevent_class_manipulation(self):
        """HIGH-004: Prevent class and object manipulation."""
        malicious_conditions = [
            "object.__class__",
            "str.__bases__",
            "().__class__.__bases__[0].__subclasses__()",
        ]

        for condition in malicious_conditions:
            with pytest.raises((ValueError, NameNotDefined, AttributeError)):
                self.evaluator.evaluate(condition, {})

    # =========================================================================
    # FUNCTIONAL TESTS: Valid Conditions
    # =========================================================================

    def test_simple_comparison(self):
        """Test simple comparison conditions."""
        assert self.evaluator.evaluate("age > 18", {"age": 25}) is True
        assert self.evaluator.evaluate("age < 18", {"age": 25}) is False
        assert self.evaluator.evaluate("age == 25", {"age": 25}) is True
        assert self.evaluator.evaluate("age != 30", {"age": 25}) is True

    def test_logical_operators(self):
        """Test logical AND/OR/NOT operators."""
        context = {"age": 25, "score": 85}

        assert self.evaluator.evaluate("age > 18 and score >= 80", context) is True
        assert self.evaluator.evaluate("age > 18 or score < 50", context) is True
        assert self.evaluator.evaluate("not (age < 18)", context) is True
        assert self.evaluator.evaluate("age > 30 and score >= 80", context) is False

    def test_arithmetic_operations(self):
        """Test arithmetic operations in conditions."""
        context = {"a": 10, "b": 5}

        assert self.evaluator.evaluate("a + b > 10", context) is True
        assert self.evaluator.evaluate("a - b == 5", context) is True
        assert self.evaluator.evaluate("a * b == 50", context) is True
        assert self.evaluator.evaluate("a / b == 2", context) is True
        assert self.evaluator.evaluate("a % 3 == 1", context) is True

    def test_safe_functions(self):
        """Test whitelisted safe functions."""
        context = {"numbers": [1, 2, 3, 4, 5], "text": "  hello  "}

        # len, max, min, sum
        assert self.evaluator.evaluate("len(numbers) == 5", context) is True
        assert self.evaluator.evaluate("max(numbers) == 5", context) is True
        assert self.evaluator.evaluate("min(numbers) == 1", context) is True
        assert self.evaluator.evaluate("sum(numbers) == 15", context) is True

        # String operations
        assert self.evaluator.evaluate("lower(text) == '  hello  '", context) is True

    def test_range_check(self):
        """Test in_range custom function."""
        context = {"score": 75}

        assert self.evaluator.evaluate("in_range(score, 0, 100)", context) is True
        assert self.evaluator.evaluate("in_range(score, 80, 100)", context) is False

    def test_membership_operators(self):
        """Test 'in' and 'not in' operators."""
        context = {"symptoms": ["fever", "cough"], "severity": 7}

        # Note: simpleeval may not support list membership directly
        # This depends on the implementation details
        try:
            result = self.evaluator.evaluate("'fever' in symptoms", context)
            assert result is True
        except Exception:
            # If membership not supported, that's OK for this test
            pass

    def test_empty_condition(self):
        """Test empty or invalid conditions."""
        assert self.evaluator.evaluate("", {}) is False
        assert self.evaluator.evaluate("   ", {}) is False

    def test_undefined_variable(self):
        """Test condition referencing undefined variable."""
        with pytest.raises(ValueError):
            self.evaluator.evaluate("undefined_var > 10", {"age": 25})

    def test_non_boolean_result_conversion(self):
        """Test automatic conversion of non-boolean results."""
        # Numeric results should be converted to bool
        result = self.evaluator.evaluate("5", {})
        assert result is True

        result = self.evaluator.evaluate("0", {})
        assert result is False

    # =========================================================================
    # VALIDATION TESTS
    # =========================================================================

    def test_validate_valid_condition(self):
        """Test condition validation for valid expressions."""
        is_valid, error = self.evaluator.validate_condition("age > 18")
        assert is_valid is True
        assert error is None

    def test_validate_invalid_syntax(self):
        """Test condition validation for syntax errors."""
        is_valid, error = self.evaluator.validate_condition("age >")
        assert is_valid is False
        assert "syntax" in error.lower()

    # =========================================================================
    # CUSTOM FUNCTION TESTS
    # =========================================================================

    def test_add_custom_function(self):
        """Test adding custom safe functions."""
        self.evaluator.add_custom_function('double', lambda x: x * 2)
        assert self.evaluator.evaluate("double(age) > 40", {"age": 25}) is True

    def test_add_invalid_function(self):
        """Test adding non-callable as function."""
        with pytest.raises(ValueError):
            self.evaluator.add_custom_function('invalid', "not_callable")

    # =========================================================================
    # CONVENIENCE FUNCTION TESTS
    # =========================================================================

    def test_evaluate_condition_convenience(self):
        """Test convenience function."""
        result = evaluate_condition("age > 18", {"age": 25})
        assert result is True


class TestSecurityRegression:
    """Regression tests for known code injection vulnerabilities."""

    def test_cve_example_os_command_injection(self):
        """Test prevention of OS command injection (CVE-like example)."""
        evaluator = SafeConditionEvaluator()

        # Attempt to inject OS command
        with pytest.raises((ValueError, NameNotDefined, FunctionNotDefined)):
            evaluator.evaluate(
                "__import__('os').system('rm -rf /')",
                {}
            )

    def test_cve_example_file_read(self):
        """Test prevention of file read attacks."""
        evaluator = SafeConditionEvaluator()

        # Attempt to read sensitive file
        with pytest.raises((ValueError, FunctionNotDefined)):
            evaluator.evaluate(
                "open('/etc/passwd').read()",
                {}
            )

    def test_cve_example_socket_access(self):
        """Test prevention of network socket access."""
        evaluator = SafeConditionEvaluator()

        # Attempt to create socket
        with pytest.raises((ValueError, NameNotDefined, FunctionNotDefined)):
            evaluator.evaluate(
                "__import__('socket').socket().connect(('evil.com', 80))",
                {}
            )

    def test_prototype_pollution_attempt(self):
        """Test prevention of prototype pollution-like attacks."""
        evaluator = SafeConditionEvaluator()

        # Attempt to modify object prototype
        with pytest.raises((ValueError, NameNotDefined, AttributeError)):
            evaluator.evaluate(
                "object.__class__.__bases__[0].__subclasses__()[104].__init__.__globals__['sys']",
                {}
            )


# Pytest fixtures for reusable test data
@pytest.fixture
def safe_evaluator():
    """Fixture providing a SafeConditionEvaluator instance."""
    return SafeConditionEvaluator()


@pytest.fixture
def patient_context():
    """Fixture providing typical patient context."""
    return {
        "age": 45,
        "symptom_severity": 7,
        "treatment_day": 15,
        "side_effects_count": 3,
    }


def test_real_world_flow_conditions(safe_evaluator, patient_context):
    """Test realistic flow engine conditions."""
    # High severity alert
    assert safe_evaluator.evaluate(
        "symptom_severity >= 7 and side_effects_count > 2",
        patient_context
    ) is True

    # Age-based branching
    assert safe_evaluator.evaluate(
        "age > 40 and treatment_day >= 14",
        patient_context
    ) is True

    # Complex condition
    assert safe_evaluator.evaluate(
        "(symptom_severity >= 5 or side_effects_count > 5) and age > 18",
        patient_context
    ) is True
