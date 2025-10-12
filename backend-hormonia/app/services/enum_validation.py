"""
Enum validation service for preventing database enum errors.

This service provides validation for enum values before database operations
to prevent InvalidTextRepresentation errors and ensure data consistency.
"""
import logging
from typing import Any, Dict, List, Optional, Type, Union
from enum import Enum

from app.models.message import MessageDirection, MessageType, MessageStatus, DeliveryStatus
from app.models.user import UserRole
from app.models.patient import FlowState
from app.models.alert import AlertSeverity, AlertStatus


logger = logging.getLogger(__name__)


class EnumValidationError(Exception):
    """Raised when enum validation fails."""
    
    def __init__(self, message: str, enum_type: str, invalid_value: Any, valid_values: List[str]):
        self.enum_type = enum_type
        self.invalid_value = invalid_value
        self.valid_values = valid_values
        super().__init__(message)


class MessageDirectionValidator:
    """Validator for MessageDirection enum values."""
    
    @staticmethod
    def validate(value: Any) -> MessageDirection:
        """
        Validate and convert value to MessageDirection enum.
        
        Args:
            value: Value to validate (string or MessageDirection)
            
        Returns:
            MessageDirection: Validated enum value
            
        Raises:
            EnumValidationError: If value is invalid
        """
        if isinstance(value, MessageDirection):
            return value
            
        if isinstance(value, str):
            # Handle both uppercase and lowercase values for backward compatibility
            normalized_value = value.upper()
            
            try:
                return MessageDirection(normalized_value)
            except ValueError:
                # Try lowercase for legacy data
                try:
                    legacy_value = value.lower()
                    if legacy_value == 'inbound':
                        return MessageDirection.INBOUND
                    elif legacy_value == 'outbound':
                        return MessageDirection.OUTBOUND
                    else:
                        raise ValueError(f"Invalid legacy value: {legacy_value}")
                except ValueError:
                    valid_values = [e.value for e in MessageDirection]
                    raise EnumValidationError(
                        f"Invalid MessageDirection value: '{value}'. Valid values are: {valid_values}",
                        "MessageDirection",
                        value,
                        valid_values
                    )
        
        raise EnumValidationError(
            f"MessageDirection value must be string or MessageDirection enum, got {type(value)}",
            "MessageDirection",
            value,
            [e.value for e in MessageDirection]
        )


class EnumValidationService:
    """
    Centralized enum validation service.
    
    Provides validation for all enum types used in the application
    to prevent database enum errors.
    """
    
    # Registry of enum validators
    _validators = {
        'MessageDirection': MessageDirectionValidator,
    }
    
    @classmethod
    def validate_message_direction(cls, value: Any) -> MessageDirection:
        """Validate MessageDirection enum value."""
        return cls._validators['MessageDirection'].validate(value)
    
    @classmethod
    def validate_message_type(cls, value: Any) -> MessageType:
        """Validate MessageType enum value."""
        if isinstance(value, MessageType):
            return value
            
        if isinstance(value, str):
            try:
                return MessageType(value.lower())
            except ValueError:
                valid_values = [e.value for e in MessageType]
                raise EnumValidationError(
                    f"Invalid MessageType value: '{value}'. Valid values are: {valid_values}",
                    "MessageType",
                    value,
                    valid_values
                )
        
        raise EnumValidationError(
            f"MessageType value must be string or MessageType enum, got {type(value)}",
            "MessageType",
            value,
            [e.value for e in MessageType]
        )
    
    @classmethod
    def validate_message_status(cls, value: Any) -> MessageStatus:
        """Validate MessageStatus enum value."""
        if isinstance(value, MessageStatus):
            return value
            
        if isinstance(value, str):
            try:
                return MessageStatus(value.lower())
            except ValueError:
                valid_values = [e.value for e in MessageStatus]
                raise EnumValidationError(
                    f"Invalid MessageStatus value: '{value}'. Valid values are: {valid_values}",
                    "MessageStatus",
                    value,
                    valid_values
                )
        
        raise EnumValidationError(
            f"MessageStatus value must be string or MessageStatus enum, got {type(value)}",
            "MessageStatus",
            value,
            [e.value for e in MessageStatus]
        )
    
    @classmethod
    def validate_user_role(cls, value: Any) -> UserRole:
        """Validate UserRole enum value."""
        if isinstance(value, UserRole):
            return value
            
        if isinstance(value, str):
            try:
                return UserRole(value.lower())
            except ValueError:
                valid_values = [e.value for e in UserRole]
                raise EnumValidationError(
                    f"Invalid UserRole value: '{value}'. Valid values are: {valid_values}",
                    "UserRole",
                    value,
                    valid_values
                )
        
        raise EnumValidationError(
            f"UserRole value must be string or UserRole enum, got {type(value)}",
            "UserRole",
            value,
            [e.value for e in UserRole]
        )
    
    @classmethod
    def validate_enum_value(cls, enum_class: Type[Enum], value: Any, allow_none: bool = False) -> Optional[Enum]:
        """
        Generic enum validation method.
        
        Args:
            enum_class: The enum class to validate against
            value: Value to validate
            allow_none: Whether to allow None values
            
        Returns:
            Validated enum value or None if allow_none=True and value is None
            
        Raises:
            EnumValidationError: If validation fails
        """
        if value is None and allow_none:
            return None
            
        if isinstance(value, enum_class):
            return value
            
        if isinstance(value, str):
            try:
                # Try exact match first
                return enum_class(value)
            except ValueError:
                # Try case-insensitive match
                for enum_value in enum_class:
                    if enum_value.value.lower() == value.lower():
                        return enum_value
                
                # If no match found, raise error
                valid_values = [e.value for e in enum_class]
                raise EnumValidationError(
                    f"Invalid {enum_class.__name__} value: '{value}'. Valid values are: {valid_values}",
                    enum_class.__name__,
                    value,
                    valid_values
                )
        
        raise EnumValidationError(
            f"{enum_class.__name__} value must be string or {enum_class.__name__} enum, got {type(value)}",
            enum_class.__name__,
            value,
            [e.value for e in enum_class]
        )
    
    @classmethod
    def get_enum_values(cls, enum_class: Type[Enum]) -> List[str]:
        """Get list of valid values for an enum class."""
        return [e.value for e in enum_class]
    
    @classmethod
    def is_valid_enum_value(cls, enum_class: Type[Enum], value: Any) -> bool:
        """Check if a value is valid for the given enum class."""
        try:
            cls.validate_enum_value(enum_class, value)
            return True
        except EnumValidationError:
            return False
    
    @classmethod
    def handle_enum_validation_error(cls, error: EnumValidationError, context: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle enum validation errors with proper logging.
        
        Args:
            error: The enum validation error
            context: Additional context for logging
        """
        log_context = {
            "enum_type": error.enum_type,
            "invalid_value": error.invalid_value,
            "valid_values": error.valid_values,
            **(context or {})
        }
        
        logger.error(
            f"Enum validation failed for {error.enum_type}: {error}",
            extra=log_context
        )


# Convenience functions for common validations
def validate_message_direction(value: Any) -> MessageDirection:
    """Convenience function for message direction validation."""
    return EnumValidationService.validate_message_direction(value)


def validate_message_type(value: Any) -> MessageType:
    """Convenience function for message type validation."""
    return EnumValidationService.validate_message_type(value)


def validate_message_status(value: Any) -> MessageStatus:
    """Convenience function for message status validation."""
    return EnumValidationService.validate_message_status(value)


def validate_user_role(value: Any) -> UserRole:
    """Convenience function for user role validation."""
    return EnumValidationService.validate_user_role(value)