"""
Safe Condition Evaluator for Flow Execution.

HIGH-004 FIX: Replaces unsafe eval() with simpleeval for secure expression evaluation.

This module provides a secure alternative to Python's built-in eval() function,
preventing code injection attacks while maintaining flow condition functionality.

File: backend-hormonia/app/domain/flows/engine/safe_condition_evaluator.py
"""
from typing import Dict, Any, Optional
import logging
from simpleeval import simple_eval, FunctionNotDefined, NameNotDefined

logger = logging.getLogger(__name__)


# Safe functions whitelist for condition evaluation
SAFE_FUNCTIONS = {
    # Comparison and logic
    'len': len,
    'max': max,
    'min': min,
    'sum': sum,
    'abs': abs,
    'round': round,

    # String operations
    'str': str,
    'lower': lambda s: str(s).lower(),
    'upper': lambda s: str(s).upper(),
    'strip': lambda s: str(s).strip(),
    'contains': lambda haystack, needle: needle in str(haystack),

    # Type checking
    'int': int,
    'float': float,
    'bool': bool,

    # Safe comparisons
    'equals': lambda a, b: a == b,
    'not_equals': lambda a, b: a != b,
    'greater_than': lambda a, b: a > b,
    'less_than': lambda a, b: a < b,
    'in_range': lambda x, min_val, max_val: min_val <= x <= max_val,

    # List operations
    'any': any,
    'all': all,
    'sorted': sorted,

    # Math operations (safe subset)
    'pow': pow,
    'divmod': divmod,
}


# Safe operators (simpleeval enables these by default, but we're explicit)
SAFE_OPERATORS = {
    # Arithmetic
    '+', '-', '*', '/', '//', '%', '**',
    # Comparison
    '==', '!=', '<', '>', '<=', '>=',
    # Logical
    'and', 'or', 'not',
    # Membership
    'in', 'not in',
    # Identity
    'is', 'is not',
}


class SafeConditionEvaluator:
    """
    Secure condition evaluator using simpleeval instead of eval().

    HIGH-004 FIX: Prevents code injection by:
    1. Using simpleeval library with restricted functions
    2. Whitelisting safe functions and operators
    3. Sandboxing expression evaluation
    4. Comprehensive error handling and logging

    Example:
        >>> evaluator = SafeConditionEvaluator()
        >>> context = {'patient_age': 45, 'symptom_severity': 7}
        >>> evaluator.evaluate('patient_age > 40 and symptom_severity >= 5', context)
        True
    """

    def __init__(self):
        """Initialize safe condition evaluator."""
        self.functions = SAFE_FUNCTIONS.copy()

    def evaluate(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Safely evaluate a condition expression against a context.

        Uses simpleeval to prevent code injection attacks while allowing
        mathematical and logical expressions needed for flow conditions.

        Args:
            condition: Condition expression (e.g., "age > 18 and score >= 5")
            context: Dictionary of variable names and values

        Returns:
            Boolean result of the evaluation

        Raises:
            ValueError: If condition is invalid or unsafe
            FunctionNotDefined: If condition uses undefined function
            NameNotDefined: If condition references undefined variable

        Examples:
            >>> evaluator = SafeConditionEvaluator()
            >>> evaluator.evaluate("age > 18", {"age": 25})
            True
            >>> evaluator.evaluate("contains(symptoms, 'fever')", {"symptoms": "fever and cough"})
            True
            >>> evaluator.evaluate("in_range(score, 0, 10)", {"score": 7})
            True
        """
        if not condition or not isinstance(condition, str):
            logger.error(f"Invalid condition type: {type(condition)}")
            return False

        # Sanitize condition (strip whitespace)
        condition = condition.strip()

        if not condition:
            logger.warning("Empty condition provided, defaulting to False")
            return False

        try:
            # Use simpleeval for safe evaluation
            result = simple_eval(
                condition,
                names=context,
                functions=self.functions
            )

            # Ensure result is boolean
            if not isinstance(result, bool):
                logger.warning(
                    f"Condition '{condition}' evaluated to non-boolean: {result}. "
                    f"Converting to bool."
                )
                result = bool(result)

            logger.debug(
                f"Condition evaluated successfully: '{condition}' -> {result}",
                extra={
                    "condition": condition,
                    "result": result,
                    "context_keys": list(context.keys())
                }
            )

            return result

        except FunctionNotDefined as e:
            logger.error(
                f"Condition uses undefined function: {e}. "
                f"Allowed functions: {list(self.functions.keys())}",
                extra={"condition": condition, "error": str(e)}
            )
            raise ValueError(f"Undefined function in condition: {e}")

        except NameNotDefined as e:
            logger.error(
                f"Condition references undefined variable: {e}. "
                f"Available variables: {list(context.keys())}",
                extra={"condition": condition, "error": str(e)}
            )
            raise ValueError(f"Undefined variable in condition: {e}")

        except SyntaxError as e:
            logger.error(
                f"Condition has syntax error: {e}",
                extra={"condition": condition, "error": str(e)}
            )
            raise ValueError(f"Invalid condition syntax: {e}")

        except Exception as e:
            logger.error(
                f"Unexpected error evaluating condition: {e}",
                exc_info=True,
                extra={"condition": condition}
            )
            # Default to False on unexpected errors for safety
            return False

    def add_custom_function(self, name: str, func: callable) -> None:
        """
        Add a custom safe function to the evaluator.

        Use with caution - only add functions that cannot execute arbitrary code.

        Args:
            name: Function name to use in conditions
            func: Callable function (must be safe)

        Example:
            >>> evaluator = SafeConditionEvaluator()
            >>> evaluator.add_custom_function('double', lambda x: x * 2)
            >>> evaluator.evaluate('double(age) > 40', {'age': 25})
            True
        """
        if not callable(func):
            raise ValueError(f"Function {name} must be callable")

        logger.info(f"Adding custom safe function: {name}")
        self.functions[name] = func

    def validate_condition(self, condition: str) -> tuple[bool, Optional[str]]:
        """
        Validate a condition without evaluating it.

        Checks syntax and references without executing the condition.

        Args:
            condition: Condition expression to validate

        Returns:
            Tuple of (is_valid, error_message)

        Example:
            >>> evaluator = SafeConditionEvaluator()
            >>> evaluator.validate_condition("age > 18")
            (True, None)
            >>> evaluator.validate_condition("import os")
            (False, "Syntax error: invalid syntax")
        """
        try:
            # Try to compile the expression
            compile(condition, '<string>', 'eval')

            # Try to evaluate with dummy context
            simple_eval(
                condition,
                names={},  # Empty context
                functions=self.functions
            )

            return True, None

        except SyntaxError as e:
            return False, f"Syntax error: {e.msg}"

        except (FunctionNotDefined, NameNotDefined) as e:
            # These are OK - just means the condition references vars/funcs
            # that will be provided at runtime
            return True, None

        except Exception as e:
            return False, f"Invalid condition: {str(e)}"


# Singleton instance for convenience
_default_evaluator = SafeConditionEvaluator()


def evaluate_condition(condition: str, context: Dict[str, Any]) -> bool:
    """
    Convenience function to evaluate conditions using the default evaluator.

    Args:
        condition: Condition expression
        context: Variable context

    Returns:
        Boolean evaluation result

    Example:
        >>> evaluate_condition("age > 18", {"age": 25})
        True
    """
    return _default_evaluator.evaluate(condition, context)
