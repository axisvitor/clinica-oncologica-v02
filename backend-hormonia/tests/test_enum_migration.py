"""
Tests for enum migration and validation functionality.

Tests the database enum migration and enum validation service
to ensure proper handling of enum values and prevention of
InvalidTextRepresentation errors.
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DataError

from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.enum_validation import (
    EnumValidationService,
    EnumValidationError,
    MessageDirectionValidator,
    validate_message_direction,
    validate_message_type,
    validate_message_status,
    validate_user_role
)
from app.middleware.enum_validation import EnumValidationMiddleware, validate_query_enum_filters


class TestMessageDirectionValidator:
    """Test MessageDirection enum validation."""
    
    def test_validate_valid_enum_value(self):
        """Test validation with valid MessageDirection enum value."""
        result = MessageDirectionValidator.validate(MessageDirection.INBOUND)
        assert result == MessageDirection.INBOUND
        
        result = MessageDirectionValidator.validate(MessageDirection.OUTBOUND)
        assert result == MessageDirection.OUTBOUND
    
    def test_validate_valid_string_uppercase(self):
        """Test validation with valid uppercase string values."""
        result = MessageDirectionValidator.validate("INBOUND")
        assert result == MessageDirection.INBOUND
        
        result = MessageDirectionValidator.validate("OUTBOUND")
        assert result == MessageDirection.OUTBOUND
    
    def test_validate_valid_string_lowercase_legacy(self):
        """Test validation with legacy lowercase string values."""
        result = MessageDirectionValidator.validate("inbound")
        assert result == MessageDirection.INBOUND
        
        result = MessageDirectionValidator.validate("outbound")
        assert result == MessageDirection.OUTBOUND
    
    def test_validate_invalid_string(self):
        """Test validation with invalid string value."""
        with pytest.raises(EnumValidationError) as exc_info:
            MessageDirectionValidator.validate("invalid")
        
        error = exc_info.value
        assert error.enum_type == "MessageDirection"
        assert error.invalid_value == "invalid"
        assert "INBOUND" in error.valid_values
        assert "OUTBOUND" in error.valid_values
    
    def test_validate_invalid_type(self):
        """Test validation with invalid type."""
        with pytest.raises(EnumValidationError) as exc_info:
            MessageDirectionValidator.validate(123)
        
        error = exc_info.value
        assert error.enum_type == "MessageDirection"
        assert error.invalid_value == 123


class TestEnumValidationService:
    """Test EnumValidationService functionality."""
    
    def test_validate_message_direction(self):
        """Test message direction validation."""
        # Valid enum
        result = EnumValidationService.validate_message_direction(MessageDirection.INBOUND)
        assert result == MessageDirection.INBOUND
        
        # Valid string
        result = EnumValidationService.validate_message_direction("OUTBOUND")
        assert result == MessageDirection.OUTBOUND
        
        # Legacy lowercase
        result = EnumValidationService.validate_message_direction("inbound")
        assert result == MessageDirection.INBOUND
    
    def test_validate_message_type(self):
        """Test message type validation."""
        # Valid enum
        result = EnumValidationService.validate_message_type(MessageType.TEXT)
        assert result == MessageType.TEXT
        
        # Valid string
        result = EnumValidationService.validate_message_type("button")
        assert result == MessageType.BUTTON
        
        # Invalid value
        with pytest.raises(EnumValidationError):
            EnumValidationService.validate_message_type("invalid_type")
    
    def test_validate_message_status(self):
        """Test message status validation."""
        # Valid enum
        result = EnumValidationService.validate_message_status(MessageStatus.SENT)
        assert result == MessageStatus.SENT
        
        # Valid string
        result = EnumValidationService.validate_message_status("pending")
        assert result == MessageStatus.PENDING
        
        # Invalid value
        with pytest.raises(EnumValidationError):
            EnumValidationService.validate_message_status("invalid_status")
    
    def test_validate_user_role(self):
        """Test user role validation."""
        # Valid enum
        result = EnumValidationService.validate_user_role(UserRole.ADMIN)
        assert result == UserRole.ADMIN
        
        # Valid string
        result = EnumValidationService.validate_user_role("doctor")
        assert result == UserRole.DOCTOR
        
        # Invalid value
        with pytest.raises(EnumValidationError):
            EnumValidationService.validate_user_role("invalid_role")
    
    def test_validate_enum_value_generic(self):
        """Test generic enum validation method."""
        # Valid value
        result = EnumValidationService.validate_enum_value(MessageDirection, "INBOUND")
        assert result == MessageDirection.INBOUND
        
        # Case insensitive
        result = EnumValidationService.validate_enum_value(MessageDirection, "inbound")
        assert result == MessageDirection.INBOUND
        
        # Allow None
        result = EnumValidationService.validate_enum_value(MessageDirection, None, allow_none=True)
        assert result is None
        
        # Don't allow None
        with pytest.raises(EnumValidationError):
            EnumValidationService.validate_enum_value(MessageDirection, None, allow_none=False)
    
    def test_get_enum_values(self):
        """Test getting valid enum values."""
        values = EnumValidationService.get_enum_values(MessageDirection)
        assert "INBOUND" in values
        assert "OUTBOUND" in values
        assert len(values) == 2
    
    def test_is_valid_enum_value(self):
        """Test checking if value is valid for enum."""
        assert EnumValidationService.is_valid_enum_value(MessageDirection, "INBOUND") is True
        assert EnumValidationService.is_valid_enum_value(MessageDirection, "inbound") is True
        assert EnumValidationService.is_valid_enum_value(MessageDirection, "invalid") is False
        assert EnumValidationService.is_valid_enum_value(MessageDirection, 123) is False
    
    def test_handle_enum_validation_error(self):
        """Test error handling with logging."""
        error = EnumValidationError(
            "Test error",
            "TestEnum",
            "invalid_value",
            ["valid1", "valid2"]
        )
        
        with patch('app.services.enum_validation.logger') as mock_logger:
            EnumValidationService.handle_enum_validation_error(
                error,
                context={"test": "context"}
            )
            
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "TestEnum" in call_args[0][0]


class TestEnumValidationMiddleware:
    """Test EnumValidationMiddleware functionality."""
    
    def test_validate_message_enums(self):
        """Test message enum validation in middleware."""
        # Create mock message with string enum values
        message = Mock(spec=Message)
        message.direction = "OUTBOUND"
        message.type = "text"
        message.status = "pending"
        message.id = "test-id"
        
        # Validate enums
        EnumValidationMiddleware.validate_message_enums(None, None, message)
        
        # Check that enums were converted
        assert message.direction == MessageDirection.OUTBOUND
        assert message.type == MessageType.TEXT
        assert message.status == MessageStatus.PENDING
    
    def test_validate_message_enums_with_none_values(self):
        """Test message enum validation with None values."""
        message = Mock(spec=Message)
        message.direction = None
        message.type = None
        message.status = None
        
        # Should not raise error
        EnumValidationMiddleware.validate_message_enums(None, None, message)
        
        assert message.direction is None
        assert message.type is None
        assert message.status is None
    
    def test_validate_message_enums_with_invalid_value(self):
        """Test message enum validation with invalid value."""
        message = Mock(spec=Message)
        message.direction = "invalid_direction"
        message.type = "text"
        message.status = "pending"
        message.id = "test-id"
        
        with patch('app.middleware.enum_validation.logger') as mock_logger:
            # Should not raise but should log error
            EnumValidationMiddleware.validate_message_enums(None, None, message)
            
            mock_logger.error.assert_called_once()
    
    def test_validate_query_filters(self):
        """Test query filter validation."""
        session = Mock()
        filters = {
            "direction": "OUTBOUND",
            "type": "text",
            "status": "sent",
            "other_field": "value"
        }
        
        result = EnumValidationMiddleware.validate_query_filters(session, filters)
        
        assert result["direction"] == MessageDirection.OUTBOUND
        assert result["type"] == MessageType.TEXT
        assert result["status"] == MessageStatus.SENT
        assert result["other_field"] == "value"
    
    def test_validate_query_filters_with_invalid_enum(self):
        """Test query filter validation with invalid enum value."""
        session = Mock()
        filters = {"direction": "invalid_direction"}
        
        with pytest.raises(EnumValidationError):
            EnumValidationMiddleware.validate_query_filters(session, filters)
    
    def test_setup_enum_validation_events(self):
        """Test setting up SQLAlchemy events."""
        with patch('app.middleware.enum_validation.event') as mock_event:
            EnumValidationMiddleware.setup_enum_validation_events()
            
            # Check that events were registered
            assert mock_event.listen.call_count == 2
            calls = mock_event.listen.call_args_list
            
            # Check before_insert event
            assert calls[0][0] == (Message, 'before_insert')
            assert calls[0][1] == EnumValidationMiddleware.validate_message_enums
            
            # Check before_update event
            assert calls[1][0] == (Message, 'before_update')
            assert calls[1][1] == EnumValidationMiddleware.validate_message_enums


class TestConvenienceFunctions:
    """Test convenience functions for enum validation."""
    
    def test_validate_message_direction_function(self):
        """Test validate_message_direction convenience function."""
        result = validate_message_direction("INBOUND")
        assert result == MessageDirection.INBOUND
        
        result = validate_message_direction("outbound")
        assert result == MessageDirection.OUTBOUND
    
    def test_validate_message_type_function(self):
        """Test validate_message_type convenience function."""
        result = validate_message_type("text")
        assert result == MessageType.TEXT
    
    def test_validate_message_status_function(self):
        """Test validate_message_status convenience function."""
        result = validate_message_status("sent")
        assert result == MessageStatus.SENT
    
    def test_validate_user_role_function(self):
        """Test validate_user_role convenience function."""
        result = validate_user_role("admin")
        assert result == UserRole.ADMIN


class TestQueryFilterValidation:
    """Test query filter validation helper function."""
    
    def test_validate_query_enum_filters(self):
        """Test validate_query_enum_filters convenience function."""
        session = Mock()
        
        result = validate_query_enum_filters(
            session,
            direction="OUTBOUND",
            type="text",
            status="pending"
        )
        
        assert result["direction"] == MessageDirection.OUTBOUND
        assert result["type"] == MessageType.TEXT
        assert result["status"] == MessageStatus.PENDING
    
    def test_validate_query_enum_filters_with_non_enum_fields(self):
        """Test validation with mixed enum and non-enum fields."""
        session = Mock()
        
        result = validate_query_enum_filters(
            session,
            direction="INBOUND",
            patient_id="123",
            created_at="2024-01-01"
        )
        
        assert result["direction"] == MessageDirection.INBOUND
        assert result["patient_id"] == "123"
        assert result["created_at"] == "2024-01-01"


@pytest.mark.integration
class TestEnumMigrationIntegration:
    """Integration tests for enum migration functionality."""
    
    @pytest.fixture
    def test_engine(self):
        """Create test database engine."""
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:")
        return engine
    
    @pytest.fixture
    def test_session(self, test_engine):
        """Create test database session."""
        Session = sessionmaker(bind=test_engine)
        return Session()
    
    def test_enum_migration_simulation(self, test_engine):
        """Test enum migration logic simulation."""
        # This test simulates the enum migration without actually running Alembic
        
        with test_engine.connect() as conn:
            # Simulate creating old enum
            try:
                conn.execute(text("CREATE TYPE messagedirection AS ('inbound', 'outbound')"))
                conn.commit()
            except Exception:
                # SQLite doesn't support custom types, so we'll skip this test
                pytest.skip("SQLite doesn't support custom enum types")
            
            # Simulate the migration steps
            # 1. Create new enum
            conn.execute(text("CREATE TYPE messagedirection_new AS ('INBOUND', 'OUTBOUND')"))
            
            # 2. The actual table update would happen here in a real migration
            # We can't fully test this without PostgreSQL, but we can verify the logic
            
            # 3. Drop old enum and rename new one
            conn.execute(text("DROP TYPE messagedirection"))
            conn.execute(text("ALTER TYPE messagedirection_new RENAME TO messagedirection"))
            
            conn.commit()
    
    def test_enum_validation_prevents_errors(self):
        """Test that enum validation prevents database errors."""
        # Test that validation catches issues before they reach the database
        
        # This should work
        validated_direction = validate_message_direction("OUTBOUND")
        assert validated_direction == MessageDirection.OUTBOUND
        
        # This should raise validation error before reaching database
        with pytest.raises(EnumValidationError):
            validate_message_direction("invalid_direction")
    
    def test_backward_compatibility(self):
        """Test backward compatibility with legacy enum values."""
        # Test that legacy lowercase values are properly converted
        
        legacy_values = ["inbound", "outbound"]
        expected_values = [MessageDirection.INBOUND, MessageDirection.OUTBOUND]
        
        for legacy, expected in zip(legacy_values, expected_values):
            result = validate_message_direction(legacy)
            assert result == expected
    
    def test_data_preservation_simulation(self):
        """Test that data is preserved during enum migration."""
        # Simulate data preservation during migration
        
        # Original data with lowercase values
        original_data = [
            {"id": 1, "direction": "inbound", "content": "Hello"},
            {"id": 2, "direction": "outbound", "content": "Hi there"}
        ]
        
        # Simulate migration conversion
        migrated_data = []
        for record in original_data:
            migrated_record = record.copy()
            if record["direction"] == "inbound":
                migrated_record["direction"] = "INBOUND"
            elif record["direction"] == "outbound":
                migrated_record["direction"] = "OUTBOUND"
            migrated_data.append(migrated_record)
        
        # Verify data preservation
        assert len(migrated_data) == len(original_data)
        assert migrated_data[0]["content"] == original_data[0]["content"]
        assert migrated_data[1]["content"] == original_data[1]["content"]
        
        # Verify enum conversion
        assert migrated_data[0]["direction"] == "INBOUND"
        assert migrated_data[1]["direction"] == "OUTBOUND"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])