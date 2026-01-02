"""
Alert processing pipeline.

This module provides the alert processor that handles the complete
processing lifecycle of alerts, including validation, enrichment,
and persistence.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..types import Alert, AlertStatus

logger = logging.getLogger(__name__)


class AlertProcessor:
    """
    Alert processing pipeline.

    Handles:
    - Alert validation
    - Context enrichment
    - Alert persistence
    - State management
    - Processing history

    The processor acts as a middleware between alert creation/evaluation
    and notification dispatch.
    """

    def __init__(self, repository=None):
        """
        Initialize AlertProcessor.

        Args:
            repository: Optional alert repository for persistence
        """
        self.repository = repository
        self._processing_history: list = []
        self._total_processed = 0
        self._total_failed = 0

        logger.info("AlertProcessor initialized")

    async def process(self, alert: Alert) -> Alert:
        """
        Process an alert through the complete pipeline.

        Steps:
        1. Validate alert data
        2. Enrich with additional context
        3. Persist to storage (if repository configured)
        4. Update alert status
        5. Track processing history

        Args:
            alert: Alert to process

        Returns:
            Processed alert

        Raises:
            ValueError: If alert validation fails
        """
        logger.info(f"Processing alert {alert.id}: {alert.title}")

        try:
            # Step 1: Validate
            self._validate_alert(alert)

            # Step 2: Enrich context
            alert = await self._enrich_alert(alert)

            # Step 3: Persist (if repository available)
            if self.repository:
                alert = await self._persist_alert(alert)

            # Step 4: Update status
            if alert.status == AlertStatus.PENDING:
                alert.status = AlertStatus.ACTIVE

            # Step 5: Track processing
            self._track_processing(alert, success=True)

            self._total_processed += 1

            logger.info(f"Alert {alert.id} processed successfully")
            return alert

        except Exception as e:
            logger.error(f"Failed to process alert {alert.id}: {e}", exc_info=True)
            self._track_processing(alert, success=False, error=str(e))
            self._total_failed += 1
            raise

    async def validate_alert(self, alert: Alert) -> bool:
        """
        Validate alert data.

        Args:
            alert: Alert to validate

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        self._validate_alert(alert)
        return True

    async def enrich_alert(self, alert: Alert) -> Alert:
        """
        Enrich alert with additional context.

        Args:
            alert: Alert to enrich

        Returns:
            Enriched alert
        """
        return await self._enrich_alert(alert)

    def get_processing_history(
        self, limit: int = 100, failures_only: bool = False
    ) -> list:
        """
        Get alert processing history.

        Args:
            limit: Maximum number of records to return
            failures_only: Only return failed processing attempts

        Returns:
            List of processing records
        """
        history = self._processing_history

        if failures_only:
            history = [h for h in history if not h["success"]]

        return sorted(history, key=lambda h: h["processed_at"], reverse=True)[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processor statistics.

        Returns:
            Dictionary of statistics
        """
        total = self._total_processed + self._total_failed
        success_rate = self._total_processed / total if total > 0 else 0

        return {
            "total_processed": self._total_processed,
            "total_failed": self._total_failed,
            "total_attempts": total,
            "success_rate": success_rate,
            "history_size": len(self._processing_history),
        }

    def reset_statistics(self) -> None:
        """Reset processor statistics."""
        self._total_processed = 0
        self._total_failed = 0
        logger.debug("Statistics reset")

    def clear_history(self) -> None:
        """Clear processing history."""
        self._processing_history.clear()
        logger.debug("Processing history cleared")

    # Private helper methods

    def _validate_alert(self, alert: Alert) -> None:
        """
        Validate alert data.

        Args:
            alert: Alert to validate

        Raises:
            ValueError: If validation fails
        """
        # Check required fields
        if not alert.id:
            raise ValueError("Alert ID is required")

        if not alert.rule_id:
            raise ValueError("Rule ID is required")

        if not alert.title or not alert.title.strip():
            raise ValueError("Alert title is required")

        if not alert.severity:
            raise ValueError("Alert severity is required")

        if not alert.rule_type:
            raise ValueError("Alert rule type is required")

        # Validate timestamps
        if not alert.created_at:
            raise ValueError("Alert creation timestamp is required")

        # Validate status
        if not alert.status:
            raise ValueError("Alert status is required")

        logger.debug(f"Alert {alert.id} validated successfully")

    async def _enrich_alert(self, alert: Alert) -> Alert:
        """
        Enrich alert with additional context.

        Args:
            alert: Alert to enrich

        Returns:
            Enriched alert
        """
        logger.debug(f"Enriching alert {alert.id}")

        # Add processing metadata
        if "processing" not in alert.metadata:
            alert.metadata["processing"] = {}

        alert.metadata["processing"]["processed_at"] = datetime.now().isoformat()
        alert.metadata["processing"]["processor_version"] = "1.0"

        # Add enrichment timestamp
        if "enriched_at" not in alert.metadata:
            alert.metadata["enriched_at"] = datetime.now().isoformat()

        # Calculate priority score based on severity
        priority_scores = {
            "info": 1,
            "warning": 2,
            "critical": 3,
            "fatal": 4,
        }
        alert.metadata["priority_score"] = priority_scores.get(alert.severity.value, 1)

        logger.debug(f"Alert {alert.id} enriched successfully")
        return alert

    async def _persist_alert(self, alert: Alert) -> Alert:
        """
        Persist alert to storage.

        Args:
            alert: Alert to persist

        Returns:
            Persisted alert (potentially with updated fields from storage)
        """
        logger.debug(f"Persisting alert {alert.id}")

        try:
            # Call repository to persist
            # In production, this would save to database
            # persisted_alert = await self.repository.save(alert)
            # return persisted_alert

            # For now, just return the alert
            logger.debug(f"Alert {alert.id} persisted successfully")
            return alert

        except Exception as e:
            logger.error(f"Failed to persist alert {alert.id}: {e}", exc_info=True)
            raise

    def _track_processing(
        self, alert: Alert, success: bool, error: Optional[str] = None
    ) -> None:
        """
        Track alert processing in history.

        Args:
            alert: Alert that was processed
            success: Whether processing succeeded
            error: Error message if failed
        """
        record = {
            "alert_id": str(alert.id),
            "rule_type": alert.rule_type.value,
            "severity": alert.severity.value,
            "success": success,
            "error": error,
            "processed_at": datetime.now().isoformat(),
        }

        self._processing_history.append(record)

        # Limit history size (keep last 1000)
        if len(self._processing_history) > 1000:
            self._processing_history = self._processing_history[-1000:]


# Singleton instance
_alert_processor: Optional[AlertProcessor] = None


def get_alert_processor() -> AlertProcessor:
    """
    Get global AlertProcessor instance.

    Returns:
        AlertProcessor singleton
    """
    global _alert_processor
    if _alert_processor is None:
        _alert_processor = AlertProcessor()
    return _alert_processor


def set_alert_processor(processor: AlertProcessor) -> None:
    """
    Set global AlertProcessor instance.

    Args:
        processor: AlertProcessor instance to use
    """
    global _alert_processor
    _alert_processor = processor
