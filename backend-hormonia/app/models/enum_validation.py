"""
Enum validation for database operations.

This module provides automatic enum validation via SQLAlchemy event listeners
before database inserts/updates to prevent InvalidTextRepresentation errors.

Moved from app/middleware/enum_validation.py - this is NOT HTTP middleware,
it contains SQLAlchemy event listeners for model validation.
"""

import logging
from typing import Any, Dict
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.message import Message
from app.services.enum_validation import EnumValidationService, EnumValidationError


logger = logging.getLogger(__name__)


class EnumValidationMiddleware:
    """Middleware for automatic enum validation in database operations."""

    @staticmethod
    def validate_message_enums(mapper, connection, target: Message) -> None:
        """
        Validate enum values for Message model before database operations.

        Args:
            mapper: SQLAlchemy mapper
            connection: Database connection
            target: Message instance being processed
        """
        try:
            # Validate direction enum
            if hasattr(target, "direction") and target.direction is not None:
                target.direction = EnumValidationService.validate_message_direction(
                    target.direction
                )

            # Validate type enum
            if hasattr(target, "type") and target.type is not None:
                target.type = EnumValidationService.validate_message_type(target.type)

            # Validate status enum
            if hasattr(target, "status") and target.status is not None:
                target.status = EnumValidationService.validate_message_status(
                    target.status
                )

        except EnumValidationError as e:
            logger.error(f"Enum validation failed for Message: {e}")
            # Log the error but don't raise to prevent breaking the operation
            # The database will still catch invalid values if they slip through
            EnumValidationService.handle_enum_validation_error(
                e,
                context={
                    "model": "Message",
                    "operation": "before_insert_or_update",
                    "message_id": getattr(target, "id", None),
                },
            )

    @staticmethod
    def setup_enum_validation_events() -> None:
        """Set up SQLAlchemy events for automatic enum validation."""
        # Register validation for Message model
        event.listen(
            Message, "before_insert", EnumValidationMiddleware.validate_message_enums
        )
        event.listen(
            Message, "before_update", EnumValidationMiddleware.validate_message_enums
        )

        logger.info("Enum validation events registered for database operations")

    @staticmethod
    def validate_query_filters(
        session: Session, query_filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate enum values in query filters before executing queries.

        Args:
            session: Database session
            query_filters: Dictionary of query filters

        Returns:
            Dict with validated enum values
        """
        validated_filters = query_filters.copy()

        try:
            # Validate message direction filters
            if "direction" in validated_filters:
                validated_filters["direction"] = (
                    EnumValidationService.validate_message_direction(
                        validated_filters["direction"]
                    )
                )

            # Validate message type filters
            if "type" in validated_filters:
                validated_filters["type"] = EnumValidationService.validate_message_type(
                    validated_filters["type"]
                )

            # Validate message status filters
            if "status" in validated_filters:
                validated_filters["status"] = (
                    EnumValidationService.validate_message_status(
                        validated_filters["status"]
                    )
                )

        except EnumValidationError as e:
            logger.error(f"Query filter validation failed: {e}")
            EnumValidationService.handle_enum_validation_error(
                e,
                context={
                    "operation": "query_filter_validation",
                    "original_filters": query_filters,
                },
            )
            # Re-raise to prevent invalid queries
            raise

        return validated_filters


# Global instance for easy access
enum_validation_middleware = EnumValidationMiddleware()


def setup_enum_validation() -> None:
    """Initialize enum validation middleware."""
    enum_validation_middleware.setup_enum_validation_events()
    logger.info("Enum validation middleware initialized")


def validate_query_enum_filters(session: Session, **filters) -> Dict[str, Any]:
    """
    Convenience function to validate enum filters in queries.

    Usage:
        filters = validate_query_enum_filters(db, direction='OUTBOUND', status='sent')
        messages = db.query(Message).filter_by(**filters).all()
    """
    return enum_validation_middleware.validate_query_filters(session, filters)
