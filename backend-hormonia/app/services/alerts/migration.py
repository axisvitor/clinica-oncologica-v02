"""
Migration helper - Maintains backward compatibility.

This module provides migration utilities and a compatibility layer
to ensure existing code continues to work with the refactored AlertManager.
"""

import logging

from .alert_manager_refactored import (
    AlertManager as RefactoredAlertManager,
    get_alert_manager as get_refactored_alert_manager,
    set_alert_manager as set_refactored_alert_manager,
)

# Import legacy imports for re-export
from .alert_manager import (
    AlertManager as LegacyAlertManager,
    get_alert_manager as get_legacy_alert_manager,
    set_alert_manager as set_legacy_alert_manager,
)

logger = logging.getLogger(__name__)

# Flag to control which version to use
USE_REFACTORED_VERSION = True  # Set to False to use legacy version


def get_alert_manager():
    """
    Get AlertManager instance (migration-aware).

    Returns refactored version by default, but can be configured
    to return legacy version for gradual migration.

    Returns:
        AlertManager instance (refactored or legacy)
    """
    if USE_REFACTORED_VERSION:
        logger.debug("Using refactored AlertManager")
        return get_refactored_alert_manager()
    else:
        logger.debug("Using legacy AlertManager")
        return get_legacy_alert_manager()


def set_alert_manager(manager):
    """
    Set AlertManager instance (migration-aware).

    Args:
        manager: AlertManager instance to set
    """
    if isinstance(manager, RefactoredAlertManager):
        set_refactored_alert_manager(manager)
    elif isinstance(manager, LegacyAlertManager):
        set_legacy_alert_manager(manager)
    else:
        logger.warning(
            f"Unknown AlertManager type: {type(manager)}. "
            "Setting as refactored version."
        )
        set_refactored_alert_manager(manager)


def migrate_to_refactored():
    """
    Migrate from legacy to refactored AlertManager.

    This function can be called during application startup
    to smoothly transition to the refactored version.
    """
    global USE_REFACTORED_VERSION

    logger.info("Migrating to refactored AlertManager...")

    try:
        # Initialize refactored version
        refactored_manager = get_refactored_alert_manager()

        # Copy any state from legacy if needed
        # (In this case, both use separate singletons, so no state to copy)

        # Switch flag
        USE_REFACTORED_VERSION = True

        logger.info("Successfully migrated to refactored AlertManager")

        return refactored_manager

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        logger.warning("Falling back to legacy AlertManager")
        USE_REFACTORED_VERSION = False
        return get_legacy_alert_manager()


def rollback_to_legacy():
    """
    Rollback to legacy AlertManager.

    Use this if issues are found with the refactored version.
    """
    global USE_REFACTORED_VERSION

    logger.warning("Rolling back to legacy AlertManager")
    USE_REFACTORED_VERSION = False

    return get_legacy_alert_manager()


class AlertManagerProxy:
    """
    Proxy that delegates to either refactored or legacy version.

    This allows code to work with either implementation transparently.
    Useful during gradual migration.
    """

    def __init__(self, use_refactored: bool = True):
        """
        Initialize proxy.

        Args:
            use_refactored: Whether to use refactored version
        """
        self.use_refactored = use_refactored
        self._manager = None

    @property
    def manager(self):
        """Get the underlying manager instance."""
        if self._manager is None:
            if self.use_refactored:
                self._manager = get_refactored_alert_manager()
            else:
                self._manager = get_legacy_alert_manager()
        return self._manager

    def __getattr__(self, name):
        """Delegate all attribute access to the underlying manager."""
        return getattr(self.manager, name)

    def switch_to_refactored(self):
        """Switch to refactored version."""
        logger.info("Switching proxy to refactored AlertManager")
        self.use_refactored = True
        self._manager = None  # Reset to force re-initialization

    def switch_to_legacy(self):
        """Switch to legacy version."""
        logger.info("Switching proxy to legacy AlertManager")
        self.use_refactored = False
        self._manager = None  # Reset to force re-initialization
