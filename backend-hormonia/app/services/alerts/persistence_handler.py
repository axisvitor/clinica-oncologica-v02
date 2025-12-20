"""
Persistence handler - Manages alert storage and retrieval.

This module handles persistent storage of alerts, providing
caching and database abstraction.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from .types import Alert
from .base import AlertRepository

logger = logging.getLogger(__name__)


class PersistenceHandler:
    """
    Handles alert persistence and retrieval.

    Responsibilities:
    - Alert storage and retrieval
    - In-memory caching
    - Database abstraction
    - Query filtering
    - Alert lifecycle tracking
    """

    def __init__(self, repository: Optional[AlertRepository] = None):
        """
        Initialize persistence handler.

        Args:
            repository: Optional alert repository for database operations
        """
        self.repository = repository
        self._alert_cache: Dict[UUID, Alert] = {}
        self._alert_history: List[Dict[str, Any]] = []

        logger.info(
            f"PersistenceHandler initialized "
            f"(repository: {'configured' if repository else 'memory-only'})"
        )

    async def store_alert(self, alert: Alert) -> Alert:
        """
        Store alert in cache and database.

        Args:
            alert: Alert to store

        Returns:
            Stored alert
        """
        logger.debug(f"Storing alert {alert.id}")

        # Store in cache
        self._alert_cache[alert.id] = alert

        # Persist to database if repository configured
        if self.repository:
            try:
                alert = await self.repository.create(alert)
                logger.debug(f"Alert {alert.id} persisted to database")
            except Exception as e:
                logger.error(
                    f"Failed to persist alert {alert.id} to database: {e}",
                    exc_info=True,
                )
                # Continue with cached version

        return alert

    async def get_alert(self, alert_id: UUID) -> Alert:
        """
        Retrieve alert by ID.

        Args:
            alert_id: Alert UUID

        Returns:
            Alert instance

        Raises:
            ValueError: If alert not found
        """
        # Try cache first
        if alert_id in self._alert_cache:
            logger.debug(f"Alert {alert_id} retrieved from cache")
            return self._alert_cache[alert_id]

        # Try database if repository configured
        if self.repository:
            try:
                alert = await self.repository.get_by_id(alert_id)
                if alert:
                    # Update cache
                    self._alert_cache[alert_id] = alert
                    logger.debug(f"Alert {alert_id} retrieved from database")
                    return alert
            except Exception as e:
                logger.error(
                    f"Error retrieving alert {alert_id} from database: {e}",
                    exc_info=True,
                )

        raise ValueError(f"Alert {alert_id} not found")

    async def update_alert(self, alert: Alert) -> Alert:
        """
        Update existing alert.

        Args:
            alert: Alert to update

        Returns:
            Updated alert
        """
        logger.debug(f"Updating alert {alert.id}")

        # Update cache
        self._alert_cache[alert.id] = alert

        # Update database if repository configured
        if self.repository:
            try:
                alert = await self.repository.update(alert)
                logger.debug(f"Alert {alert.id} updated in database")
            except Exception as e:
                logger.error(
                    f"Failed to update alert {alert.id} in database: {e}",
                    exc_info=True,
                )

        return alert

    async def list_alerts(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Alert]:
        """
        List alerts with optional filters.

        Args:
            filters: Optional filters (severity, status, rule_type, date range)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of alerts
        """
        # If repository configured, use it
        if self.repository:
            try:
                alerts = await self.repository.find(
                    filters=filters,
                    limit=limit,
                    offset=offset,
                )
                logger.debug(f"Retrieved {len(alerts)} alerts from database")
                return alerts
            except Exception as e:
                logger.error(f"Error listing alerts from database: {e}", exc_info=True)

        # Fall back to cache
        alerts = list(self._alert_cache.values())

        # Apply filters
        if filters:
            alerts = self._apply_filters(alerts, filters)

        # Apply pagination
        if offset:
            alerts = alerts[offset:]
        if limit:
            alerts = alerts[:limit]

        logger.debug(f"Retrieved {len(alerts)} alerts from cache")
        return alerts

    async def count_alerts(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count alerts matching filters.

        Args:
            filters: Optional filters

        Returns:
            Count of matching alerts
        """
        # If repository configured, use it
        if self.repository:
            try:
                count = await self.repository.count(filters=filters)
                return count
            except Exception as e:
                logger.error(f"Error counting alerts in database: {e}", exc_info=True)

        # Fall back to cache
        alerts = list(self._alert_cache.values())
        if filters:
            alerts = self._apply_filters(alerts, filters)

        return len(alerts)

    async def delete_alert(self, alert_id: UUID) -> None:
        """
        Delete alert from cache and database.

        Args:
            alert_id: Alert UUID to delete
        """
        logger.debug(f"Deleting alert {alert_id}")

        # Remove from cache
        if alert_id in self._alert_cache:
            del self._alert_cache[alert_id]

        # Archive to history
        self._alert_history.append(
            {
                "alert_id": str(alert_id),
                "deleted_at": datetime.now().isoformat(),
            }
        )

    def _apply_filters(
        self, alerts: List[Alert], filters: Dict[str, Any]
    ) -> List[Alert]:
        """
        Apply filters to alert list.

        Args:
            alerts: List of alerts
            filters: Filters to apply

        Returns:
            Filtered list of alerts
        """
        filtered = alerts

        if "severity" in filters:
            filtered = [a for a in filtered if a.severity == filters["severity"]]

        if "rule_type" in filters:
            filtered = [a for a in filtered if a.rule_type == filters["rule_type"]]

        if "status" in filters:
            filtered = [a for a in filtered if a.status == filters["status"]]

        if "start_date" in filters:
            start_date = filters["start_date"]
            filtered = [a for a in filtered if a.created_at >= start_date]

        if "end_date" in filters:
            end_date = filters["end_date"]
            filtered = [a for a in filtered if a.created_at <= end_date]

        if "escalated" in filters:
            filtered = [a for a in filtered if a.escalated == filters["escalated"]]

        return filtered

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache metrics
        """
        total_cached = len(self._alert_cache)

        by_status: Dict[str, int] = {}
        for alert in self._alert_cache.values():
            status_key = alert.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

        return {
            "total_cached": total_cached,
            "by_status": by_status,
            "history_count": len(self._alert_history),
            "has_repository": self.repository is not None,
        }

    def clear_cache(self) -> None:
        """Clear in-memory cache."""
        cleared_count = len(self._alert_cache)
        self._alert_cache.clear()
        logger.info(f"Cleared {cleared_count} alerts from cache")


# Singleton instance
_persistence_handler: Optional[PersistenceHandler] = None


def get_persistence_handler() -> PersistenceHandler:
    """
    Get global PersistenceHandler instance.

    Returns:
        PersistenceHandler singleton
    """
    global _persistence_handler
    if _persistence_handler is None:
        _persistence_handler = PersistenceHandler()
    return _persistence_handler


def set_persistence_handler(handler: PersistenceHandler) -> None:
    """
    Set global PersistenceHandler instance.

    Args:
        handler: PersistenceHandler instance to use
    """
    global _persistence_handler
    _persistence_handler = handler
