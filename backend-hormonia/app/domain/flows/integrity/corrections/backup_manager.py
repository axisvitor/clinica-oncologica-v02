"""
Backup manager for data correction operations.
"""

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class BackupManager:
    """Manager for creating and managing correction backups."""

    @staticmethod
    def create_flow_state_backup(
        flow_state, field_name: str, original_value: Any
    ) -> dict[str, Any]:
        """
        Create backup data for flow state correction.

        Args:
            flow_state: Flow state being corrected
            field_name: Name of field being corrected
            original_value: Original value before correction

        Returns:
            Backup data dictionary
        """
        return {
            f"original_{field_name}": original_value,
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_message_backup(
        message, field_name: str, original_value: Any
    ) -> dict[str, Any]:
        """
        Create backup data for message correction.

        Args:
            message: Message being corrected
            field_name: Name of field being corrected
            original_value: Original value before correction

        Returns:
            Backup data dictionary
        """
        return {
            f"original_{field_name}": original_value,
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_flow_message_backup(flow_message) -> dict[str, Any]:
        """
        Create complete backup for flow message deletion.

        Args:
            flow_message: Flow message being deleted

        Returns:
            Backup data dictionary
        """
        backup_data = {
            "flow_message_data": {
                "id": str(flow_message.id),
                "flow_state_id": str(flow_message.flow_state_id),
                "content": flow_message.content,
            },
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"Backup created for orphaned flow message: {backup_data}")
        return backup_data

    @staticmethod
    def create_duplicate_flows_backup(
        kept_flow, completed_flows: list
    ) -> dict[str, Any]:
        """
        Create backup for duplicate flows resolution.

        Args:
            kept_flow: Flow being kept active
            completed_flows: Flows being completed

        Returns:
            Backup data dictionary
        """
        return {
            "completed_flows": [str(f.id) for f in completed_flows],
            "kept_flow": str(kept_flow.id),
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def store_backup_in_state_data(entity, backup_data: dict[str, Any]) -> None:
        """
        Store backup data in entity's state_data or metadata field.

        Args:
            entity: Entity to store backup in
            backup_data: Backup data to store
        """
        if hasattr(entity, "state_data"):
            entity.state_data = entity.state_data or {}
            entity.state_data["correction_backup"] = backup_data
        elif hasattr(entity, "message_metadata"):
            entity.message_metadata = entity.message_metadata or {}
            entity.message_metadata["correction_backup"] = backup_data
