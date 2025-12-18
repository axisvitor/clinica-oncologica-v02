"""
Unified Status Mapping System for Monthly Quiz

This module provides a centralized system for converting between different
status representations used in the quiz system.

Status Systems:
1. QuizLinkStatus: ACTIVE, EXPIRED, USED, CANCELLED
2. QuizSession status: in_progress, completed, cancelled
3. Frontend MonthlyQuizLink status: active, expired, completed, cancelled
"""

from enum import Enum
from typing import Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)


class UnifiedQuizStatus(str, Enum):
    """Unified status enum for consistent status handling across the system."""

    # Core statuses
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    USED = "used"  # For link-specific tracking


class QuizLinkStatus(str, Enum):
    """Quiz link status enum (maintained for backward compatibility)."""

    ACTIVE = "active"
    EXPIRED = "expired"
    USED = "used"
    CANCELLED = "cancelled"


class QuizSessionStatus(str, Enum):
    """Quiz session status enum (maintained for backward compatibility)."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StatusMappingError(Exception):
    """Raised when status mapping fails."""

    pass


class StatusMapper:
    """Centralized status mapping service."""

    # Mapping from QuizLinkStatus to UnifiedQuizStatus
    LINK_TO_UNIFIED: Dict[str, str] = {
        QuizLinkStatus.ACTIVE: UnifiedQuizStatus.ACTIVE,
        QuizLinkStatus.EXPIRED: UnifiedQuizStatus.EXPIRED,
        QuizLinkStatus.USED: UnifiedQuizStatus.USED,
        QuizLinkStatus.CANCELLED: UnifiedQuizStatus.CANCELLED,
    }

    # Mapping from QuizSessionStatus to UnifiedQuizStatus
    SESSION_TO_UNIFIED: Dict[str, str] = {
        QuizSessionStatus.IN_PROGRESS: UnifiedQuizStatus.IN_PROGRESS,
        QuizSessionStatus.COMPLETED: UnifiedQuizStatus.COMPLETED,
        QuizSessionStatus.CANCELLED: UnifiedQuizStatus.CANCELLED,
    }

    # Mapping from UnifiedQuizStatus to QuizLinkStatus
    UNIFIED_TO_LINK: Dict[str, str] = {
        UnifiedQuizStatus.ACTIVE: QuizLinkStatus.ACTIVE,
        UnifiedQuizStatus.EXPIRED: QuizLinkStatus.EXPIRED,
        UnifiedQuizStatus.USED: QuizLinkStatus.USED,
        UnifiedQuizStatus.CANCELLED: QuizLinkStatus.CANCELLED,
        # Special mappings for session statuses
        UnifiedQuizStatus.IN_PROGRESS: QuizLinkStatus.ACTIVE,  # Session in progress = link still active
        UnifiedQuizStatus.COMPLETED: QuizLinkStatus.USED,  # Session completed = link was used
    }

    # Mapping from UnifiedQuizStatus to QuizSessionStatus
    UNIFIED_TO_SESSION: Dict[str, str] = {
        UnifiedQuizStatus.IN_PROGRESS: QuizSessionStatus.IN_PROGRESS,
        UnifiedQuizStatus.COMPLETED: QuizSessionStatus.COMPLETED,
        UnifiedQuizStatus.CANCELLED: QuizSessionStatus.CANCELLED,
        # Special mappings for link statuses
        UnifiedQuizStatus.ACTIVE: QuizSessionStatus.IN_PROGRESS,  # Active link = session in progress
        UnifiedQuizStatus.USED: QuizSessionStatus.COMPLETED,  # Used link = session completed
        UnifiedQuizStatus.EXPIRED: QuizSessionStatus.CANCELLED,  # Expired link = session cancelled
    }

    @classmethod
    def link_to_unified(
        cls, link_status: Union[str, QuizLinkStatus]
    ) -> UnifiedQuizStatus:
        """Convert QuizLinkStatus to UnifiedQuizStatus."""
        status_str = str(link_status)

        if status_str not in cls.LINK_TO_UNIFIED:
            logger.warning(f"Unknown link status: {status_str}")
            raise StatusMappingError(
                f"Cannot map link status '{status_str}' to unified status"
            )

        unified = cls.LINK_TO_UNIFIED[status_str]
        logger.debug(f"Mapped link status '{status_str}' to unified '{unified}'")
        return UnifiedQuizStatus(unified)

    @classmethod
    def session_to_unified(
        cls, session_status: Union[str, QuizSessionStatus]
    ) -> UnifiedQuizStatus:
        """Convert QuizSessionStatus to UnifiedQuizStatus."""
        status_str = str(session_status)

        if status_str not in cls.SESSION_TO_UNIFIED:
            logger.warning(f"Unknown session status: {status_str}")
            raise StatusMappingError(
                f"Cannot map session status '{status_str}' to unified status"
            )

        unified = cls.SESSION_TO_UNIFIED[status_str]
        logger.debug(f"Mapped session status '{status_str}' to unified '{unified}'")
        return UnifiedQuizStatus(unified)

    @classmethod
    def unified_to_link(
        cls, unified_status: Union[str, UnifiedQuizStatus]
    ) -> QuizLinkStatus:
        """Convert UnifiedQuizStatus to QuizLinkStatus."""
        status_str = str(unified_status)

        if status_str not in cls.UNIFIED_TO_LINK:
            logger.warning(f"Unknown unified status for link mapping: {status_str}")
            raise StatusMappingError(
                f"Cannot map unified status '{status_str}' to link status"
            )

        link = cls.UNIFIED_TO_LINK[status_str]
        logger.debug(f"Mapped unified status '{status_str}' to link '{link}'")
        return QuizLinkStatus(link)

    @classmethod
    def unified_to_session(
        cls, unified_status: Union[str, UnifiedQuizStatus]
    ) -> QuizSessionStatus:
        """Convert UnifiedQuizStatus to QuizSessionStatus."""
        status_str = str(unified_status)

        if status_str not in cls.UNIFIED_TO_SESSION:
            logger.warning(f"Unknown unified status for session mapping: {status_str}")
            raise StatusMappingError(
                f"Cannot map unified status '{status_str}' to session status"
            )

        session = cls.UNIFIED_TO_SESSION[status_str]
        logger.debug(f"Mapped unified status '{status_str}' to session '{session}'")
        return QuizSessionStatus(session)

    @classmethod
    def link_to_session(
        cls, link_status: Union[str, QuizLinkStatus]
    ) -> QuizSessionStatus:
        """Direct conversion from QuizLinkStatus to QuizSessionStatus."""
        try:
            unified = cls.link_to_unified(link_status)
            return cls.unified_to_session(unified)
        except StatusMappingError as e:
            logger.error(f"Failed to convert link status to session status: {e}")
            raise

    @classmethod
    def session_to_link(
        cls, session_status: Union[str, QuizSessionStatus]
    ) -> QuizLinkStatus:
        """Direct conversion from QuizSessionStatus to QuizLinkStatus."""
        try:
            unified = cls.session_to_unified(session_status)
            return cls.unified_to_link(unified)
        except StatusMappingError as e:
            logger.error(f"Failed to convert session status to link status: {e}")
            raise

    @classmethod
    def is_active_status(
        cls, status: Union[str, UnifiedQuizStatus, QuizLinkStatus, QuizSessionStatus]
    ) -> bool:
        """Check if a status indicates an active/accessible state."""
        status_str = str(status)
        active_statuses = {
            UnifiedQuizStatus.ACTIVE,
            UnifiedQuizStatus.IN_PROGRESS,
            QuizLinkStatus.ACTIVE,
            QuizSessionStatus.IN_PROGRESS,
        }
        return status_str in [str(s) for s in active_statuses]

    @classmethod
    def is_completed_status(
        cls, status: Union[str, UnifiedQuizStatus, QuizLinkStatus, QuizSessionStatus]
    ) -> bool:
        """Check if a status indicates completion."""
        status_str = str(status)
        completed_statuses = {
            UnifiedQuizStatus.COMPLETED,
            UnifiedQuizStatus.USED,
            QuizSessionStatus.COMPLETED,
            QuizLinkStatus.USED,
        }
        return status_str in [str(s) for s in completed_statuses]

    @classmethod
    def is_terminated_status(
        cls, status: Union[str, UnifiedQuizStatus, QuizLinkStatus, QuizSessionStatus]
    ) -> bool:
        """Check if a status indicates termination (cancelled/expired)."""
        status_str = str(status)
        terminated_statuses = {
            UnifiedQuizStatus.CANCELLED,
            UnifiedQuizStatus.EXPIRED,
            QuizLinkStatus.CANCELLED,
            QuizLinkStatus.EXPIRED,
            QuizSessionStatus.CANCELLED,
        }
        return status_str in [str(s) for s in terminated_statuses]

    @classmethod
    def get_frontend_status(
        cls,
        link_status: Optional[Union[str, QuizLinkStatus]] = None,
        session_status: Optional[Union[str, QuizSessionStatus]] = None,
    ) -> str:
        """
        Get the appropriate frontend status based on link and/or session status.

        Frontend expects: 'active', 'expired', 'completed', 'cancelled'

        Priority logic:
        1. If session is completed -> 'completed'
        2. If session is cancelled -> 'cancelled'
        3. If link is expired -> 'expired'
        4. If link is cancelled -> 'cancelled'
        5. If session is in_progress -> 'active'
        6. If link is active -> 'active'
        7. Default -> 'active'
        """
        try:
            # Convert to unified status for consistent handling
            unified_session = None
            unified_link = None

            if session_status:
                unified_session = cls.session_to_unified(session_status)

            if link_status:
                unified_link = cls.link_to_unified(link_status)

            # Priority logic
            if unified_session == UnifiedQuizStatus.COMPLETED:
                return "completed"
            elif unified_session == UnifiedQuizStatus.CANCELLED:
                return "cancelled"
            elif unified_link == UnifiedQuizStatus.EXPIRED:
                return "expired"
            elif unified_link == UnifiedQuizStatus.CANCELLED:
                return "cancelled"
            elif unified_session == UnifiedQuizStatus.IN_PROGRESS:
                return "active"
            elif unified_link == UnifiedQuizStatus.ACTIVE:
                return "active"
            else:
                return "active"  # Default fallback

        except StatusMappingError as e:
            logger.warning(
                f"Error mapping frontend status: {e}. Using default 'active'"
            )
            return "active"

    @classmethod
    def validate_status_consistency(
        cls,
        link_status: Union[str, QuizLinkStatus],
        session_status: Union[str, QuizSessionStatus],
    ) -> Dict[str, Union[bool, str]]:
        """
        Validate that link and session statuses are logically consistent.

        Returns:
            Dict with 'is_valid' boolean and 'message' string
        """
        try:
            unified_link = cls.link_to_unified(link_status)
            unified_session = cls.session_to_unified(session_status)

            # Define valid combinations
            valid_combinations = {
                (UnifiedQuizStatus.ACTIVE, UnifiedQuizStatus.IN_PROGRESS),
                (UnifiedQuizStatus.USED, UnifiedQuizStatus.COMPLETED),
                (UnifiedQuizStatus.CANCELLED, UnifiedQuizStatus.CANCELLED),
                (UnifiedQuizStatus.EXPIRED, UnifiedQuizStatus.CANCELLED),
                # Additional valid states
                (
                    UnifiedQuizStatus.ACTIVE,
                    UnifiedQuizStatus.CANCELLED,
                ),  # User cancelled after link was active
            }

            combination = (unified_link, unified_session)

            if combination in valid_combinations:
                return {
                    "is_valid": True,
                    "message": f"Status combination {link_status}:{session_status} is valid",
                }
            else:
                return {
                    "is_valid": False,
                    "message": f"Status combination {link_status}:{session_status} is inconsistent. "
                    f"Unified mapping: {unified_link}:{unified_session}",
                }

        except StatusMappingError as e:
            return {"is_valid": False, "message": f"Status validation failed: {e}"}


# Export the main mapper instance
status_mapper = StatusMapper()


# Convenience functions for common operations
def map_link_to_session(link_status: Union[str, QuizLinkStatus]) -> QuizSessionStatus:
    """Convenience function to map link status to session status."""
    return status_mapper.link_to_session(link_status)


def map_session_to_link(
    session_status: Union[str, QuizSessionStatus],
) -> QuizLinkStatus:
    """Convenience function to map session status to link status."""
    return status_mapper.session_to_link(session_status)


def get_frontend_status(
    link_status: Optional[str] = None, session_status: Optional[str] = None
) -> str:
    """Convenience function to get frontend-compatible status."""
    return status_mapper.get_frontend_status(link_status, session_status)


def validate_status_consistency(
    link_status: str, session_status: str
) -> Dict[str, Union[bool, str]]:
    """Convenience function to validate status consistency."""
    return status_mapper.validate_status_consistency(link_status, session_status)
