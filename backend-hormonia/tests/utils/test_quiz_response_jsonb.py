"""
Tests for JSONB Quiz Response Value Utilities.

Tests cover serialization, deserialization, validation, and querying
of the quiz_responses.response_value JSONB column.

Migration: HIGH-003 - response_value Text to JSONB conversion
"""
from app.utils.quiz_response_jsonb import (
    ResponseValueSerializer,
    ResponseValueDeserializer,
    ResponseValueValidator,
    serialize_response,
    deserialize_to_text,
    deserialize_to_array,
    deserialize_to_numeric,
    validate_response_value
)


class TestResponseValueSerializer:
    """Test JSONB serialization."""

    def test_plain_text_serialization(self):
        """Test plain text serialization."""
        result = ResponseValueSerializer.to_plain_text("Simple answer")
        assert result == "Simple answer"
        assert isinstance(result, str)

    def test_text_object_serialization(self):
        """Test text object with metadata serialization."""
        result = ResponseValueSerializer.to_text_object(
            "Answer text",
            confidence=0.95,
            language="pt-BR"
        )
        assert result == {
            "text": "Answer text",
            "confidence": 0.95,
            "language": "pt-BR"
        }

    def test_array_serialization(self):
        """Test array serialization for multiple choice."""
        result = ResponseValueSerializer.to_array(["A", "B", "C"])
        assert result == ["A", "B", "C"]
        assert isinstance(result, list)

    def test_selections_object_serialization(self):
        """Test selections object with metadata."""
        result = ResponseValueSerializer.to_selections_object(
            ["Option 1", "Option 2"],
            timestamp="2025-01-14T12:00:00Z"
        )
        assert result == {
            "selections": ["Option 1", "Option 2"],
            "timestamp": "2025-01-14T12:00:00Z"
        }

    def test_scale_serialization(self):
        """Test scale response serialization."""
        result = ResponseValueSerializer.to_scale(7, min_value=1, max_value=10)
        assert result == {
            "value": 7,
            "type": "scale",
            "range": {"min": 1, "max": 10}
        }

    def test_boolean_serialization(self):
        """Test boolean response serialization."""
        result = ResponseValueSerializer.to_boolean("yes", True)
        assert result == {
            "text": "yes",
            "boolean": True
        }

    def test_auto_serialize_text(self):
        """Test auto-serialization of text."""
        result = ResponseValueSerializer.auto_serialize("Simple text")
        assert result == "Simple text"

    def test_auto_serialize_multiple_choice(self):
        """Test auto-serialization of comma-separated values."""
        result = ResponseValueSerializer.auto_serialize("A, B, C", "multiple_choice")
        assert result == ["A", "B", "C"]

    def test_auto_serialize_boolean(self):
        """Test auto-serialization of boolean-like text."""
        result = ResponseValueSerializer.auto_serialize("yes")
        assert result == {"text": "yes", "boolean": True}

        result = ResponseValueSerializer.auto_serialize("no")
        assert result == {"text": "no", "boolean": False}

    def test_auto_serialize_json_string(self):
        """Test auto-serialization of JSON string."""
        json_str = '{"key": "value"}'
        result = ResponseValueSerializer.auto_serialize(json_str)
        assert result == {"key": "value"}

    def test_auto_serialize_list(self):
        """Test auto-serialization of list."""
        result = ResponseValueSerializer.auto_serialize(["A", "B"])
        assert result == ["A", "B"]

    def test_auto_serialize_dict(self):
        """Test auto-serialization of dict."""
        data = {"text": "answer", "meta": "data"}
        result = ResponseValueSerializer.auto_serialize(data)
        assert result == data

    def test_auto_serialize_numeric_scale(self):
        """Test auto-serialization of numeric scale."""
        result = ResponseValueSerializer.auto_serialize(8, "scale")
        assert result == {
            "value": 8,
            "type": "scale",
            "range": {"min": 1, "max": 10}
        }


class TestResponseValueDeserializer:
    """Test JSONB deserialization."""

    def test_deserialize_plain_text(self):
        """Test deserializing plain text."""
        result = ResponseValueDeserializer.to_text("Simple answer")
        assert result == "Simple answer"

    def test_deserialize_text_object(self):
        """Test deserializing text object."""
        result = ResponseValueDeserializer.to_text({"text": "Answer"})
        assert result == "Answer"

    def test_deserialize_array_to_text(self):
        """Test deserializing array to text."""
        result = ResponseValueDeserializer.to_text(["A", "B", "C"])
        assert result == "A, B, C"

    def test_deserialize_selections_object_to_text(self):
        """Test deserializing selections object to text."""
        result = ResponseValueDeserializer.to_text({"selections": ["X", "Y"]})
        assert result == "X, Y"

    def test_deserialize_scale_to_text(self):
        """Test deserializing scale to text."""
        result = ResponseValueDeserializer.to_text({"value": 7, "type": "scale"})
        assert result == "7"

    def test_deserialize_to_array_from_list(self):
        """Test deserializing list to array."""
        result = ResponseValueDeserializer.to_array(["A", "B", "C"])
        assert result == ["A", "B", "C"]

    def test_deserialize_to_array_from_text(self):
        """Test deserializing text to array."""
        result = ResponseValueDeserializer.to_array("Single value")
        assert result == ["Single value"]

    def test_deserialize_to_array_from_comma_separated(self):
        """Test deserializing comma-separated to array."""
        result = ResponseValueDeserializer.to_array("A, B, C")
        assert result == ["A", "B", "C"]

    def test_deserialize_to_array_from_selections(self):
        """Test deserializing selections object to array."""
        result = ResponseValueDeserializer.to_array({"selections": ["X", "Y"]})
        assert result == ["X", "Y"]

    def test_deserialize_to_numeric_from_number(self):
        """Test deserializing number to numeric."""
        result = ResponseValueDeserializer.to_numeric(7)
        assert result == 7.0

    def test_deserialize_to_numeric_from_string(self):
        """Test deserializing string number to numeric."""
        result = ResponseValueDeserializer.to_numeric("8.5")
        assert result == 8.5

    def test_deserialize_to_numeric_from_object(self):
        """Test deserializing scale object to numeric."""
        result = ResponseValueDeserializer.to_numeric({"value": 9})
        assert result == 9.0

    def test_deserialize_to_numeric_invalid(self):
        """Test deserializing invalid numeric."""
        result = ResponseValueDeserializer.to_numeric("not a number")
        assert result is None

    def test_deserialize_to_boolean_true(self):
        """Test deserializing true boolean."""
        assert ResponseValueDeserializer.to_boolean(True) is True
        assert ResponseValueDeserializer.to_boolean("yes") is True
        assert ResponseValueDeserializer.to_boolean("sim") is True
        assert ResponseValueDeserializer.to_boolean({"boolean": True}) is True

    def test_deserialize_to_boolean_false(self):
        """Test deserializing false boolean."""
        assert ResponseValueDeserializer.to_boolean(False) is False
        assert ResponseValueDeserializer.to_boolean("no") is False
        assert ResponseValueDeserializer.to_boolean("não") is False
        assert ResponseValueDeserializer.to_boolean({"boolean": False}) is False

    def test_deserialize_to_boolean_invalid(self):
        """Test deserializing invalid boolean."""
        result = ResponseValueDeserializer.to_boolean("maybe")
        assert result is None


class TestResponseValueValidator:
    """Test JSONB validation."""

    def test_validate_format_valid(self):
        """Test validating valid formats."""
        valid_values = [
            "text",
            123,
            True,
            ["A", "B"],
            {"key": "value"}
        ]
        for value in valid_values:
            is_valid, error = ResponseValueValidator.validate_format(value)
            assert is_valid, f"Value {value} should be valid"
            assert error is None

    def test_validate_format_none(self):
        """Test validating None."""
        is_valid, error = ResponseValueValidator.validate_format(None)
        assert not is_valid
        assert "cannot be None" in error

    def test_validate_multiple_choice_valid(self):
        """Test validating valid multiple choice."""
        is_valid, error = ResponseValueValidator.validate_multiple_choice(
            ["A", "B"],
            valid_options=["A", "B", "C", "D"]
        )
        assert is_valid
        assert error is None

    def test_validate_multiple_choice_invalid_option(self):
        """Test validating invalid multiple choice option."""
        is_valid, error = ResponseValueValidator.validate_multiple_choice(
            ["A", "X"],
            valid_options=["A", "B", "C"]
        )
        assert not is_valid
        assert "Invalid selections" in error

    def test_validate_multiple_choice_empty(self):
        """Test validating empty multiple choice."""
        is_valid, error = ResponseValueValidator.validate_multiple_choice([])
        assert not is_valid
        assert "No selections" in error

    def test_validate_scale_valid(self):
        """Test validating valid scale."""
        is_valid, error = ResponseValueValidator.validate_scale(
            {"value": 7},
            min_value=1,
            max_value=10
        )
        assert is_valid
        assert error is None

    def test_validate_scale_out_of_range(self):
        """Test validating scale out of range."""
        is_valid, error = ResponseValueValidator.validate_scale(
            {"value": 15},
            min_value=1,
            max_value=10
        )
        assert not is_valid
        assert "out of range" in error

    def test_validate_scale_non_numeric(self):
        """Test validating non-numeric scale."""
        is_valid, error = ResponseValueValidator.validate_scale("not a number")
        assert not is_valid
        assert "must be numeric" in error

    def test_validate_text_valid(self):
        """Test validating valid text."""
        is_valid, error = ResponseValueValidator.validate_text(
            "Valid response text",
            min_length=5,
            max_length=100
        )
        assert is_valid
        assert error is None

    def test_validate_text_too_short(self):
        """Test validating text too short."""
        is_valid, error = ResponseValueValidator.validate_text(
            "Hi",
            min_length=5
        )
        assert not is_valid
        assert "too short" in error

    def test_validate_text_too_long(self):
        """Test validating text too long."""
        is_valid, error = ResponseValueValidator.validate_text(
            "x" * 1000,
            max_length=100
        )
        assert not is_valid
        assert "too long" in error

    def test_validate_text_empty(self):
        """Test validating empty text."""
        is_valid, error = ResponseValueValidator.validate_text("")
        assert not is_valid
        assert "cannot be empty" in error


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_serialize_response(self):
        """Test serialize_response convenience function."""
        result = serialize_response("Answer text")
        assert result == "Answer text"

        result = serialize_response(["A", "B"], "multiple_choice")
        assert result == ["A", "B"]

    def test_deserialize_to_text(self):
        """Test deserialize_to_text convenience function."""
        result = deserialize_to_text({"text": "Answer"})
        assert result == "Answer"

    def test_deserialize_to_array(self):
        """Test deserialize_to_array convenience function."""
        result = deserialize_to_array(["A", "B"])
        assert result == ["A", "B"]

    def test_deserialize_to_numeric(self):
        """Test deserialize_to_numeric convenience function."""
        result = deserialize_to_numeric({"value": 8})
        assert result == 8.0

    def test_validate_response_value_multiple_choice(self):
        """Test validate_response_value for multiple choice."""
        is_valid, error = validate_response_value(
            ["A", "B"],
            "multiple_choice",
            options=["A", "B", "C"]
        )
        assert is_valid

    def test_validate_response_value_scale(self):
        """Test validate_response_value for scale."""
        is_valid, error = validate_response_value(
            {"value": 7},
            "scale",
            min_value=1,
            max_value=10
        )
        assert is_valid

    def test_validate_response_value_text(self):
        """Test validate_response_value for text."""
        is_valid, error = validate_response_value(
            "Good response",
            "open_text",
            min_length=5
        )
        assert is_valid


class TestRoundTripConversion:
    """Test round-trip serialization and deserialization."""

    def test_text_round_trip(self):
        """Test text round trip."""
        original = "Sample answer"
        serialized = serialize_response(original)
        deserialized = deserialize_to_text(serialized)
        assert deserialized == original

    def test_array_round_trip(self):
        """Test array round trip."""
        original = ["A", "B", "C"]
        serialized = serialize_response(original)
        deserialized = deserialize_to_array(serialized)
        assert deserialized == original

    def test_scale_round_trip(self):
        """Test scale round trip."""
        original = 7
        serialized = serialize_response(original, "scale")
        deserialized = deserialize_to_numeric(serialized)
        assert deserialized == float(original)

    def test_complex_object_round_trip(self):
        """Test complex object round trip."""
        original = {
            "text": "Answer",
            "confidence": 0.95,
            "metadata": {"lang": "pt-BR"}
        }
        serialized = serialize_response(original)
        deserialized_text = deserialize_to_text(serialized)
        assert deserialized_text == "Answer"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_null_handling(self):
        """Test handling of None/NULL values."""
        result = serialize_response(None)
        assert result == ""

        result = deserialize_to_text(None)
        assert result == ""

        result = deserialize_to_array(None)
        assert result == []

    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        result = serialize_response("")
        assert result == ""

        result = deserialize_to_text("")
        assert result == ""

    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        original = "Resposta com acentuação: São Paulo, Brasília"
        serialized = serialize_response(original)
        deserialized = deserialize_to_text(serialized)
        assert deserialized == original

    def test_special_characters(self):
        """Test handling of special characters."""
        original = "Response with 'quotes', \"double quotes\", and \\backslash"
        serialized = serialize_response(original)
        deserialized = deserialize_to_text(serialized)
        assert deserialized == original

    def test_very_long_text(self):
        """Test handling of very long text."""
        original = "x" * 10000
        serialized = serialize_response(original)
        deserialized = deserialize_to_text(serialized)
        assert deserialized == original

    def test_mixed_type_array(self):
        """Test handling of mixed type arrays."""
        original = ["A", 1, True, "B"]
        serialized = serialize_response(original)
        deserialized = deserialize_to_array(serialized)
        assert deserialized == ["A", "1", "True", "B"]

    def test_nested_objects(self):
        """Test handling of nested objects."""
        original = {
            "text": "Answer",
            "metadata": {
                "nested": {
                    "deeply": "value"
                }
            }
        }
        serialized = serialize_response(original)
        assert serialized == original

    def test_malformed_json_string(self):
        """Test handling of malformed JSON string."""
        malformed = '{"incomplete": '
        serialized = serialize_response(malformed)
        # Should treat as plain text since JSON parsing fails
        assert isinstance(serialized, str)
        assert serialized == malformed
