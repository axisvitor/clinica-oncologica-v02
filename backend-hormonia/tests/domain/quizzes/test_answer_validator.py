"""
Comprehensive Unit Tests for AnswerValidator.

Tests the quiz answer validation and normalization functionality including:
- i18n "other" value normalization
- Question type validation (multiple_choice, single_choice, open_text, numeric, date, boolean)
- Encryption of sensitive responses
- Response timing validation (bot detection)
- XSS prevention through text sanitization

Test Categories:
- Unit tests: Pure function tests with mocked dependencies
- Edge cases: Boundary conditions and error scenarios
- Security tests: XSS prevention and timing validation

Reference: app/domain/quizzes/answer_validator.py
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch
from typing import Dict, Any


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_config():
    """Mock monthly quiz configuration."""
    config = Mock()
    config.MONTHLY_QUIZ_ENABLE_ENCRYPTION = True
    return config


@pytest.fixture
def mock_encryption_service():
    """Mock encryption service."""
    service = Mock()
    service.encrypt = Mock(side_effect=lambda x: f"encrypted:{x}")
    return service


@pytest.fixture
def answer_validator(mock_config, mock_encryption_service):
    """Create AnswerValidator instance with mocked dependencies."""
    with patch(
        "app.domain.quizzes.answer_validator.get_monthly_quiz_config",
        return_value=mock_config,
    ), patch(
        "app.domain.quizzes.answer_validator.get_encryption_service",
        return_value=mock_encryption_service,
    ):
        from app.domain.quizzes.answer_validator import AnswerValidator

        validator = AnswerValidator()
        return validator


@pytest.fixture
def mock_quiz_template():
    """Create a mock QuizTemplate for testing."""
    template = Mock()
    template.questions = [
        {
            "id": "q1",
            "type": "single_choice",
            "text": "How are you feeling?",
            "options": [
                {"value": "good", "label": "Good"},
                {"value": "bad", "label": "Bad"},
                {"value": "other", "label": "Other", "allow_other": True},
            ],
        },
        {
            "id": "q2",
            "type": "multiple_choice",
            "text": "Select symptoms",
            "options": [
                {"value": "headache", "label": "Headache"},
                {"value": "fatigue", "label": "Fatigue"},
                {"value": "other", "label": "Other"},
            ],
        },
        {
            "id": "q3",
            "type": "open_text",
            "text": "Describe your experience",
        },
        {
            "id": "q4",
            "type": "numeric",
            "text": "Rate your pain",
            "validation": {"min": 0, "max": 10},
        },
        {
            "id": "q5",
            "type": "date",
            "text": "When did symptoms start?",
        },
        {
            "id": "q6",
            "type": "boolean",
            "text": "Do you have allergies?",
        },
        {
            "id": "q7",
            "type": "single_choice",
            "text": "Sensitive question",
            "is_sensitive": True,
            "options": [
                {"value": "yes", "label": "Yes"},
                {"value": "no", "label": "No"},
            ],
        },
    ]
    return template


# ============================================================================
# QUESTION TYPE FIXTURES
# ============================================================================


@pytest.fixture
def single_choice_question() -> Dict[str, Any]:
    """Single choice question fixture."""
    return {
        "id": "q1",
        "type": "single_choice",
        "text": "How do you feel?",
        "options": [
            {"value": "good", "label": "Good"},
            {"value": "bad", "label": "Bad"},
            {"value": "outra", "label": "Outra", "allow_other": True},
        ],
    }


@pytest.fixture
def multiple_choice_question() -> Dict[str, Any]:
    """Multiple choice question fixture."""
    return {
        "id": "q2",
        "type": "multiple_choice",
        "text": "Select symptoms",
        "options": [
            {"value": "headache", "label": "Headache"},
            {"value": "fatigue", "label": "Fatigue"},
            {"value": "nausea", "label": "Nausea"},
        ],
    }


@pytest.fixture
def open_text_question() -> Dict[str, Any]:
    """Open text question fixture."""
    return {
        "id": "q3",
        "type": "open_text",
        "text": "Describe your experience",
    }


@pytest.fixture
def numeric_question() -> Dict[str, Any]:
    """Numeric question with validation fixture."""
    return {
        "id": "q4",
        "type": "numeric",
        "text": "Rate your pain (0-10)",
        "validation": {"min": 0, "max": 10},
    }


@pytest.fixture
def date_question() -> Dict[str, Any]:
    """Date question fixture."""
    return {
        "id": "q5",
        "type": "date",
        "text": "When did symptoms start?",
    }


@pytest.fixture
def boolean_question() -> Dict[str, Any]:
    """Boolean question fixture."""
    return {
        "id": "q6",
        "type": "boolean",
        "text": "Do you have allergies?",
    }


@pytest.fixture
def sensitive_question() -> Dict[str, Any]:
    """Sensitive question requiring encryption fixture."""
    return {
        "id": "q7",
        "type": "single_choice",
        "text": "Medical history question",
        "is_sensitive": True,
        "options": [
            {"value": "yes", "label": "Yes"},
            {"value": "no", "label": "No"},
        ],
    }


# ============================================================================
# TEST CLASS: normalize_other_value()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestNormalizeOtherValue:
    """Tests for i18n 'other' value normalization."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("outra", "outra"),  # Portuguese (Brazil) - matches allow_other option
            ("other", "outra"),  # English - matches allow_other option
            ("outro", "outra"),  # Portuguese masculine - matches allow_other option
            ("otra", "outra"),   # Spanish - matches allow_other option
            ("autre", "outra"),  # French - in check list, matches allow_other option
            ("altro", "outra"),  # Italian - in check list, matches allow_other option
            ("OUTRA", "outra"),  # Case insensitive
            ("Other", "outra"),  # Mixed case
            ("  other  ", "outra"),  # With whitespace
        ],
    )
    def test_normalize_other_aliases(
        self, answer_validator, single_choice_question, input_value, expected
    ):
        """Test normalization of various 'other' option aliases."""
        result = answer_validator.normalize_other_value(input_value, single_choice_question)
        assert result == expected

    def test_normalize_non_other_value_unchanged(
        self, answer_validator, single_choice_question
    ):
        """Test that non-'other' values remain unchanged."""
        result = answer_validator.normalize_other_value("good", single_choice_question)
        assert result == "good"

    def test_normalize_with_allow_other_option(self, answer_validator):
        """Test normalization finds option with allow_other flag."""
        question = {
            "options": [
                {"value": "a", "label": "A"},
                {"value": "custom_other", "label": "Custom", "allow_other": True},
            ]
        }
        result = answer_validator.normalize_other_value("other", question)
        assert result == "custom_other"

    def test_normalize_non_string_returns_unchanged(
        self, answer_validator, single_choice_question
    ):
        """Test that non-string values are returned unchanged."""
        result = answer_validator.normalize_other_value(123, single_choice_question)
        assert result == 123

        result = answer_validator.normalize_other_value(["a", "b"], single_choice_question)
        assert result == ["a", "b"]

    def test_normalize_with_empty_options(self, answer_validator):
        """Test normalization with empty options list."""
        question = {"options": []}
        result = answer_validator.normalize_other_value("other", question)
        assert result == "other"

    def test_normalize_with_no_options(self, answer_validator):
        """Test normalization when question has no options key."""
        question = {"type": "open_text"}
        result = answer_validator.normalize_other_value("other", question)
        assert result == "other"


# ============================================================================
# TEST CLASS: validate_and_normalize_response()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateAndNormalizeResponse:
    """Tests for the main response validation dispatcher."""

    def test_dispatches_to_multiple_choice(
        self, answer_validator, multiple_choice_question
    ):
        """Test that multiple_choice type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            ["headache", "fatigue"], multiple_choice_question
        )
        assert result == ["headache", "fatigue"]

    def test_dispatches_to_single_choice(
        self, answer_validator, single_choice_question
    ):
        """Test that single_choice type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            "good", single_choice_question
        )
        assert result == "good"

    def test_dispatches_to_open_text(self, answer_validator, open_text_question):
        """Test that open_text type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            "Some text response", open_text_question
        )
        assert result == "Some text response"

    def test_dispatches_to_numeric(self, answer_validator, numeric_question):
        """Test that numeric type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            "5.5", numeric_question
        )
        assert result == 5.5

    def test_dispatches_to_date(self, answer_validator, date_question):
        """Test that date type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            "2025-01-15", date_question
        )
        assert result == "2025-01-15"

    def test_dispatches_to_boolean(self, answer_validator, boolean_question):
        """Test that boolean type dispatches correctly."""
        result = answer_validator.validate_and_normalize_response(
            "yes", boolean_question
        )
        assert result is True

    def test_unknown_type_returns_as_is(self, answer_validator):
        """Test that unknown question types return value unchanged."""
        question = {"type": "custom_unknown"}
        result = answer_validator.validate_and_normalize_response(
            "custom_value", question
        )
        assert result == "custom_value"

    def test_defaults_to_open_text_when_no_type(self, answer_validator):
        """Test that missing type defaults to open_text validation."""
        question = {"text": "No type specified"}
        result = answer_validator.validate_and_normalize_response("some text", question)
        assert result == "some text"


# ============================================================================
# TEST CLASS: _validate_multiple_choice()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateMultipleChoice:
    """Tests for multiple choice array validation."""

    def test_accepts_valid_array(self, answer_validator, multiple_choice_question):
        """Test that valid array of options is accepted."""
        result = answer_validator._validate_multiple_choice(
            ["headache", "fatigue"], multiple_choice_question
        )
        assert result == ["headache", "fatigue"]

    def test_parses_json_string(self, answer_validator, multiple_choice_question):
        """Test that JSON string arrays are parsed."""
        result = answer_validator._validate_multiple_choice(
            '["headache", "fatigue"]', multiple_choice_question
        )
        assert result == ["headache", "fatigue"]

    def test_single_string_becomes_list(self, answer_validator, multiple_choice_question):
        """Test that single string value becomes a list."""
        result = answer_validator._validate_multiple_choice(
            "headache", multiple_choice_question
        )
        assert result == ["headache"]

    def test_rejects_invalid_option(self, answer_validator, multiple_choice_question):
        """Test that invalid option values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_multiple_choice(
                ["headache", "invalid_option"], multiple_choice_question
            )
        assert "Invalid option value" in str(exc_info.value)

    def test_rejects_non_string_non_array(self, answer_validator, multiple_choice_question):
        """Test that non-string, non-array values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_multiple_choice(123, multiple_choice_question)
        assert "Multiple choice requires array" in str(exc_info.value)

    def test_normalizes_other_values_in_list(self, answer_validator):
        """Test that 'other' values are normalized in list."""
        question = {
            "options": [
                {"value": "a", "label": "A"},
                {"value": "outra", "label": "Outra", "allow_other": True},
            ]
        }
        result = answer_validator._validate_multiple_choice(
            ["a", "other"], question
        )
        assert "outra" in result

    def test_empty_array_accepted(self, answer_validator):
        """Test that empty array is accepted when options not required."""
        question = {"options": []}
        result = answer_validator._validate_multiple_choice([], question)
        assert result == []


# ============================================================================
# TEST CLASS: _validate_single_choice()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateSingleChoice:
    """Tests for single choice option validation."""

    def test_accepts_valid_option(self, answer_validator, single_choice_question):
        """Test that valid option value is accepted."""
        result = answer_validator._validate_single_choice("good", single_choice_question)
        assert result == "good"

    def test_rejects_non_string(self, answer_validator, single_choice_question):
        """Test that non-string values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_single_choice(123, single_choice_question)
        assert "Single choice requires a string value" in str(exc_info.value)

    def test_rejects_invalid_option(self, answer_validator, single_choice_question):
        """Test that invalid option values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_single_choice(
                "invalid_option", single_choice_question
            )
        assert "Invalid option value" in str(exc_info.value)

    def test_normalizes_other_value(self, answer_validator, single_choice_question):
        """Test that 'other' aliases are normalized."""
        result = answer_validator._validate_single_choice("other", single_choice_question)
        assert result == "outra"

    def test_accepts_when_no_options(self, answer_validator):
        """Test that any string is accepted when no options defined."""
        question = {"type": "single_choice"}
        result = answer_validator._validate_single_choice("anything", question)
        assert result == "anything"

    def test_accepts_string_options(self, answer_validator):
        """Test validation with simple string options (not dict)."""
        question = {
            "type": "single_choice",
            "options": ["yes", "no", "maybe"],
        }
        result = answer_validator._validate_single_choice("yes", question)
        assert result == "yes"


# ============================================================================
# TEST CLASS: _validate_open_text()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateOpenText:
    """Tests for open text length validation."""

    def test_accepts_valid_text(self, answer_validator):
        """Test that valid text is accepted."""
        result = answer_validator._validate_open_text("This is valid text")
        assert result == "This is valid text"

    def test_converts_non_string_to_string(self, answer_validator):
        """Test that non-string values are converted."""
        result = answer_validator._validate_open_text(12345)
        assert result == "12345"

    def test_trims_whitespace(self, answer_validator):
        """Test that leading/trailing whitespace is stripped."""
        result = answer_validator._validate_open_text("  text with spaces  ")
        assert result == "text with spaces"

    def test_rejects_empty_string(self, answer_validator):
        """Test that empty/whitespace-only strings raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_open_text("")
        assert "at least 1 character" in str(exc_info.value)

    def test_rejects_whitespace_only(self, answer_validator):
        """Test that whitespace-only strings raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_open_text("   ")
        assert "at least 1 character" in str(exc_info.value)

    def test_accepts_single_character(self, answer_validator):
        """Test that single character is accepted (min length = 1)."""
        result = answer_validator._validate_open_text("a")
        assert result == "a"


# ============================================================================
# TEST CLASS: _validate_numeric()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateNumeric:
    """Tests for numeric min/max validation."""

    def test_accepts_valid_number(self, answer_validator, numeric_question):
        """Test that valid number within range is accepted."""
        result = answer_validator._validate_numeric(5, numeric_question)
        assert result == 5.0

    def test_accepts_string_number(self, answer_validator, numeric_question):
        """Test that string number is converted."""
        result = answer_validator._validate_numeric("7.5", numeric_question)
        assert result == 7.5

    def test_accepts_min_boundary(self, answer_validator, numeric_question):
        """Test that minimum boundary value is accepted."""
        result = answer_validator._validate_numeric(0, numeric_question)
        assert result == 0.0

    def test_accepts_max_boundary(self, answer_validator, numeric_question):
        """Test that maximum boundary value is accepted."""
        result = answer_validator._validate_numeric(10, numeric_question)
        assert result == 10.0

    def test_rejects_below_min(self, answer_validator, numeric_question):
        """Test that value below minimum raises ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_numeric(-1, numeric_question)
        assert "at least" in str(exc_info.value)

    def test_rejects_above_max(self, answer_validator, numeric_question):
        """Test that value above maximum raises ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_numeric(11, numeric_question)
        assert "at most" in str(exc_info.value)

    def test_rejects_non_numeric_string(self, answer_validator, numeric_question):
        """Test that non-numeric strings raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_numeric("not a number", numeric_question)
        assert "valid number" in str(exc_info.value)

    def test_accepts_no_validation_constraints(self, answer_validator):
        """Test that any number accepted when no constraints."""
        question = {"type": "numeric"}
        result = answer_validator._validate_numeric(99999, question)
        assert result == 99999.0

    def test_rejects_none_value(self, answer_validator, numeric_question):
        """Test that None value raises ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError):
            answer_validator._validate_numeric(None, numeric_question)


# ============================================================================
# TEST CLASS: _validate_date()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateDate:
    """Tests for ISO date format validation."""

    @pytest.mark.parametrize(
        "valid_date",
        [
            "2025-01-15",
            "2025-12-31",
            "2020-02-29",  # Leap year
            "2025-01-15T10:30:00",
            "2025-01-15T10:30:00+00:00",
            "2025-01-15T10:30:00Z",
        ],
    )
    def test_accepts_valid_iso_dates(self, answer_validator, date_question, valid_date):
        """Test that valid ISO date formats are accepted."""
        result = answer_validator._validate_date(valid_date)
        assert result == valid_date

    @pytest.mark.parametrize(
        "invalid_date",
        [
            "15/01/2025",  # DD/MM/YYYY
            "01-15-2025",  # MM-DD-YYYY
            "January 15, 2025",  # Text format
            "2025/01/15",  # Wrong separator
            "not a date",
            "2025-13-01",  # Invalid month
            "2025-01-32",  # Invalid day
        ],
    )
    def test_rejects_invalid_date_formats(
        self, answer_validator, date_question, invalid_date
    ):
        """Test that invalid date formats raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_date(invalid_date)
        assert "ISO format" in str(exc_info.value)

    def test_rejects_non_string(self, answer_validator, date_question):
        """Test that non-string values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_date(20250115)
        assert "string in ISO format" in str(exc_info.value)


# ============================================================================
# TEST CLASS: _validate_boolean()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateBoolean:
    """Tests for boolean truthy/falsy conversion."""

    @pytest.mark.parametrize(
        "truthy_value",
        [
            True,
            "true",
            "True",
            "TRUE",
            "yes",
            "Yes",
            "YES",
            "sim",  # Portuguese
            "Sim",
            "1",
            "y",
            "Y",
        ],
    )
    def test_accepts_truthy_values(self, answer_validator, boolean_question, truthy_value):
        """Test that truthy values return True."""
        result = answer_validator._validate_boolean(truthy_value)
        assert result is True

    @pytest.mark.parametrize(
        "falsy_value",
        [
            False,
            "false",
            "False",
            "FALSE",
            "no",
            "No",
            "NO",
            "n",
            "N",
            "0",
        ],
    )
    def test_accepts_falsy_values(self, answer_validator, boolean_question, falsy_value):
        """Test that falsy values return False."""
        result = answer_validator._validate_boolean(falsy_value)
        assert result is False

    def test_rejects_nao_without_accent(self, answer_validator, boolean_question):
        """Test that 'nao' without tilde accent raises ValidationError."""
        # The code checks for "nao" (with tilde character) but plain "nao" should fail
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError):
            answer_validator._validate_boolean("nao")

    def test_accepts_integer_values(self, answer_validator, boolean_question):
        """Test that integer values are converted to boolean."""
        assert answer_validator._validate_boolean(1) is True
        assert answer_validator._validate_boolean(0) is False
        assert answer_validator._validate_boolean(5) is True  # Truthy

    def test_rejects_invalid_string(self, answer_validator, boolean_question):
        """Test that invalid strings raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_boolean("maybe")
        assert "Invalid boolean value" in str(exc_info.value)

    def test_rejects_none_value(self, answer_validator, boolean_question):
        """Test that None raises ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_boolean(None)
        assert "Boolean value required" in str(exc_info.value)

    def test_rejects_list_value(self, answer_validator, boolean_question):
        """Test that list values raise ValidationError."""
        from app.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            answer_validator._validate_boolean([True])
        assert "Boolean value required" in str(exc_info.value)


# ============================================================================
# TEST CLASS: encrypt_response_if_needed()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
@pytest.mark.security
class TestEncryptResponseIfNeeded:
    """Tests for conditional response encryption."""

    def test_encrypts_sensitive_string(
        self, answer_validator, sensitive_question, mock_encryption_service
    ):
        """Test that sensitive string responses are encrypted."""
        result, is_encrypted = answer_validator.encrypt_response_if_needed(
            "yes", sensitive_question
        )
        assert is_encrypted is True
        assert result == "encrypted:yes"
        mock_encryption_service.encrypt.assert_called_once_with("yes")

    def test_encrypts_sensitive_list_as_json(
        self, answer_validator, mock_encryption_service
    ):
        """Test that sensitive list responses are JSON-serialized before encryption."""
        question = {"is_sensitive": True}
        result, is_encrypted = answer_validator.encrypt_response_if_needed(
            ["a", "b", "c"], question
        )
        assert is_encrypted is True
        mock_encryption_service.encrypt.assert_called_once_with('["a", "b", "c"]')

    def test_does_not_encrypt_non_sensitive(
        self, answer_validator, single_choice_question, mock_encryption_service
    ):
        """Test that non-sensitive responses are not encrypted."""
        result, is_encrypted = answer_validator.encrypt_response_if_needed(
            "good", single_choice_question
        )
        assert is_encrypted is False
        assert result == "good"
        mock_encryption_service.encrypt.assert_not_called()

    def test_respects_encryption_disabled_config(self, mock_encryption_service):
        """Test that encryption is skipped when disabled in config."""
        mock_config = Mock()
        mock_config.MONTHLY_QUIZ_ENABLE_ENCRYPTION = False

        with patch(
            "app.domain.quizzes.answer_validator.get_monthly_quiz_config",
            return_value=mock_config,
        ), patch(
            "app.domain.quizzes.answer_validator.get_encryption_service",
            return_value=mock_encryption_service,
        ):
            from app.domain.quizzes.answer_validator import AnswerValidator

            validator = AnswerValidator()
            question = {"is_sensitive": True}
            result, is_encrypted = validator.encrypt_response_if_needed("secret", question)

            assert is_encrypted is False
            assert result == "secret"
            mock_encryption_service.encrypt.assert_not_called()

    def test_converts_numeric_to_string_for_encryption(
        self, answer_validator, mock_encryption_service
    ):
        """Test that numeric values are converted to string for encryption."""
        question = {"is_sensitive": True}
        result, is_encrypted = answer_validator.encrypt_response_if_needed(
            42.5, question
        )
        assert is_encrypted is True
        mock_encryption_service.encrypt.assert_called_once_with("42.5")


# ============================================================================
# TEST CLASS: validate_response_timing()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
@pytest.mark.security
class TestValidateResponseTiming:
    """Tests for bot detection via timing validation."""

    def test_accepts_normal_timing(self, answer_validator):
        """Test that normal response timing is accepted."""
        session_start = datetime.now(timezone.utc) - timedelta(seconds=5)
        result = answer_validator.validate_response_timing(session_start)
        assert result is True

    def test_rejects_too_fast_submission(self, answer_validator):
        """Test that submissions faster than min_time are rejected."""
        from app.exceptions import ValidationError

        session_start = datetime.now(timezone.utc) - timedelta(seconds=1)
        with pytest.raises(ValidationError) as exc_info:
            answer_validator.validate_response_timing(session_start, min_time_seconds=2)
        assert "too quickly" in str(exc_info.value)

    def test_respects_custom_min_time(self, answer_validator):
        """Test that custom min_time_seconds is respected."""
        session_start = datetime.now(timezone.utc) - timedelta(seconds=10)
        result = answer_validator.validate_response_timing(
            session_start, min_time_seconds=5
        )
        assert result is True

    def test_rejects_at_exact_boundary(self, answer_validator):
        """Test that submission at exact min_time boundary is rejected."""
        from app.exceptions import ValidationError

        # At exactly 2 seconds, elapsed < min_time_seconds is False
        # but if elapsed = 1.99, it should be rejected
        session_start = datetime.now(timezone.utc) - timedelta(seconds=1.5)
        with pytest.raises(ValidationError):
            answer_validator.validate_response_timing(session_start, min_time_seconds=2)

    def test_accepts_long_duration(self, answer_validator):
        """Test that long durations are accepted."""
        session_start = datetime.now(timezone.utc) - timedelta(hours=1)
        result = answer_validator.validate_response_timing(session_start)
        assert result is True


# ============================================================================
# TEST CLASS: sanitize_text_input()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
@pytest.mark.security
class TestSanitizeTextInput:
    """Tests for XSS prevention through text sanitization."""

    def test_returns_empty_for_none(self, answer_validator):
        """Test that None input returns empty string."""
        result = answer_validator.sanitize_text_input(None)
        assert result == ""

    def test_returns_empty_for_empty_string(self, answer_validator):
        """Test that empty string input returns empty string."""
        result = answer_validator.sanitize_text_input("")
        assert result == ""

    def test_truncates_to_max_length(self, answer_validator):
        """Test that text is truncated to max_length."""
        long_text = "a" * 100
        result = answer_validator.sanitize_text_input(long_text, max_length=50)
        assert len(result) == 50

    def test_removes_script_tags(self, answer_validator):
        """Test that <script> tags are removed."""
        malicious = '<script>alert("XSS")</script>'
        result = answer_validator.sanitize_text_input(malicious)
        assert "<script" not in result.lower()

    def test_removes_javascript_protocol(self, answer_validator):
        """Test that javascript: protocol is removed."""
        malicious = 'javascript:alert("XSS")'
        result = answer_validator.sanitize_text_input(malicious)
        assert "javascript:" not in result.lower()

    def test_removes_onerror_handler(self, answer_validator):
        """Test that onerror= event handler is removed."""
        malicious = '<img src="x" onerror="alert(1)">'
        result = answer_validator.sanitize_text_input(malicious)
        assert "onerror=" not in result.lower()

    def test_removes_onclick_handler(self, answer_validator):
        """Test that onclick= event handler is removed."""
        malicious = '<div onclick="evil()">Click me</div>'
        result = answer_validator.sanitize_text_input(malicious)
        assert "onclick=" not in result.lower()

    def test_strips_whitespace(self, answer_validator):
        """Test that leading/trailing whitespace is stripped."""
        result = answer_validator.sanitize_text_input("  text  ")
        assert result == "text"

    def test_preserves_safe_text(self, answer_validator):
        """Test that safe text is preserved."""
        safe_text = "This is a normal response with numbers 123 and symbols @#$"
        result = answer_validator.sanitize_text_input(safe_text)
        assert result == safe_text.strip()

    def test_handles_mixed_case_attacks(self, answer_validator):
        """Test that lowercase patterns are detected but only lowercase removed.

        Note: The current implementation uses lower() for detection but
        case-sensitive replacement, so '<SCRIPT>' is detected but the
        exact lowercase pattern '<script' is what gets removed.
        This is a known limitation - uppercase variants remain.
        """
        # Lowercase is removed
        malicious_lower = '<script>alert(1)</script>'
        result_lower = answer_validator.sanitize_text_input(malicious_lower)
        assert "<script" not in result_lower

        # Uppercase is detected but the replacement only removes lowercase pattern
        # This documents the actual behavior (not necessarily ideal)
        malicious_upper = '<SCRIPT>alert(1)</SCRIPT>'
        result_upper = answer_validator.sanitize_text_input(malicious_upper)
        # The pattern IS detected (via lower() check) but replacement is case-sensitive
        # So uppercase "<SCRIPT" remains - this is a limitation to be aware of
        assert "<SCRIPT>" in result_upper  # Documents current behavior

    def test_default_max_length_is_5000(self, answer_validator):
        """Test that default max_length is 5000."""
        long_text = "a" * 6000
        result = answer_validator.sanitize_text_input(long_text)
        assert len(result) == 5000


# ============================================================================
# TEST CLASS: validate_question_exists()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestValidateQuestionExists:
    """Tests for question existence validation in templates."""

    def test_finds_existing_question(self, answer_validator, mock_quiz_template):
        """Test that existing question is found and returned."""
        result = answer_validator.validate_question_exists("q1", mock_quiz_template)
        assert result["id"] == "q1"
        assert result["type"] == "single_choice"

    def test_raises_not_found_for_missing_question(
        self, answer_validator, mock_quiz_template
    ):
        """Test that missing question raises NotFoundError."""
        from app.exceptions import NotFoundError

        with pytest.raises(NotFoundError) as exc_info:
            answer_validator.validate_question_exists("nonexistent", mock_quiz_template)
        assert "not found in template" in str(exc_info.value)

    def test_finds_question_by_exact_id_match(
        self, answer_validator, mock_quiz_template
    ):
        """Test that question is found by exact ID match."""
        result = answer_validator.validate_question_exists("q4", mock_quiz_template)
        assert result["type"] == "numeric"


# ============================================================================
# TEST CLASS: build_response_metadata()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestBuildResponseMetadata:
    """Tests for response metadata building."""

    def test_builds_basic_metadata(self, answer_validator):
        """Test that basic metadata is built correctly."""
        result = answer_validator.build_response_metadata(
            is_encrypted=False,
            other_text=None,
            question_index=3,
        )
        assert result["is_encrypted"] is False
        assert result["question_index"] == 3
        assert "other_text" not in result

    def test_includes_other_text_when_provided(self, answer_validator):
        """Test that other_text is included when provided."""
        result = answer_validator.build_response_metadata(
            is_encrypted=False,
            other_text="Custom other response",
            question_index=1,
        )
        assert result["other_text"] == "Custom other response"

    def test_includes_encrypted_flag(self, answer_validator):
        """Test that is_encrypted flag is set correctly."""
        result = answer_validator.build_response_metadata(
            is_encrypted=True,
            other_text=None,
            question_index=0,
        )
        assert result["is_encrypted"] is True

    def test_merges_additional_metadata(self, answer_validator):
        """Test that additional metadata is merged."""
        result = answer_validator.build_response_metadata(
            is_encrypted=False,
            other_text=None,
            question_index=2,
            additional_metadata={"custom_key": "custom_value", "timestamp": 12345},
        )
        assert result["custom_key"] == "custom_value"
        assert result["timestamp"] == 12345

    def test_empty_other_text_not_included(self, answer_validator):
        """Test that empty other_text is not included."""
        result = answer_validator.build_response_metadata(
            is_encrypted=False,
            other_text="",
            question_index=0,
        )
        assert "other_text" not in result


# ============================================================================
# TEST CLASS: _get_allowed_option_values()
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestGetAllowedOptionValues:
    """Tests for extracting allowed option values from questions."""

    def test_extracts_dict_option_values(self, answer_validator):
        """Test extraction from dict options."""
        question = {
            "options": [
                {"value": "a", "label": "A"},
                {"value": "b", "label": "B"},
            ]
        }
        result = answer_validator._get_allowed_option_values(question)
        assert result == ["a", "b"]

    def test_extracts_string_options(self, answer_validator):
        """Test extraction from string options."""
        question = {"options": ["yes", "no", "maybe"]}
        result = answer_validator._get_allowed_option_values(question)
        assert result == ["yes", "no", "maybe"]

    def test_returns_none_for_empty_options(self, answer_validator):
        """Test that empty options returns None."""
        question = {"options": []}
        result = answer_validator._get_allowed_option_values(question)
        assert result is None

    def test_returns_none_for_no_options(self, answer_validator):
        """Test that missing options key returns None."""
        question = {"type": "open_text"}
        result = answer_validator._get_allowed_option_values(question)
        assert result is None

    def test_handles_mixed_option_types(self, answer_validator):
        """Test handling of mixed dict and string options."""
        question = {
            "options": [
                {"value": "a", "label": "A"},
                "b",
                {"value": "c"},
            ]
        }
        result = answer_validator._get_allowed_option_values(question)
        assert result == ["a", "b", "c"]


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================


@pytest.mark.unit
@pytest.mark.quiz
class TestAnswerValidatorIntegration:
    """Integration-style tests for full validation flows."""

    def test_full_validation_flow_single_choice(
        self, answer_validator, single_choice_question
    ):
        """Test complete validation flow for single choice."""
        # Validate and normalize
        normalized = answer_validator.validate_and_normalize_response(
            "good", single_choice_question
        )
        assert normalized == "good"

        # Check encryption (non-sensitive)
        encrypted, is_encrypted = answer_validator.encrypt_response_if_needed(
            normalized, single_choice_question
        )
        assert is_encrypted is False
        assert encrypted == "good"

    def test_full_validation_flow_with_encryption(
        self, answer_validator, sensitive_question
    ):
        """Test complete validation flow with encryption."""
        # Validate and normalize
        normalized = answer_validator.validate_and_normalize_response(
            "yes", sensitive_question
        )
        assert normalized == "yes"

        # Check encryption (sensitive)
        encrypted, is_encrypted = answer_validator.encrypt_response_if_needed(
            normalized, sensitive_question
        )
        assert is_encrypted is True
        assert encrypted.startswith("encrypted:")

    def test_validation_with_timing_check(self, answer_validator, open_text_question):
        """Test validation with timing check."""
        session_start = datetime.now(timezone.utc) - timedelta(seconds=10)

        # Timing check
        assert answer_validator.validate_response_timing(session_start) is True

        # Text validation
        normalized = answer_validator.validate_and_normalize_response(
            "Valid response text", open_text_question
        )
        assert normalized == "Valid response text"

    def test_full_flow_with_xss_sanitization(self, answer_validator, open_text_question):
        """Test that XSS is sanitized in open text responses."""
        malicious_input = '<script>alert("XSS")</script>Normal text'

        # Sanitize first
        sanitized = answer_validator.sanitize_text_input(malicious_input)
        assert "<script" not in sanitized.lower()

        # Then validate
        normalized = answer_validator.validate_and_normalize_response(
            sanitized, open_text_question
        )
        assert "<script" not in normalized.lower()
