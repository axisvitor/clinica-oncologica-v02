"""
HIPAA-Compliant Audit Logger.

Provides comprehensive audit trail for healthcare data access and modifications
with 7-year retention as required by HIPAA regulations.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
import json
import redis.asyncio as redis

from app.utils.logging import get_logger


logger = get_logger(__name__)


class AuditAction(str, Enum):
    """Audit actions for HIPAA compliance."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    EXPORT = "export"
    PRINT = "print"
    SHARE = "share"
    EMERGENCY_ACCESS = "emergency_access"


class ResourceType(str, Enum):
    """Resource types for audit logging."""

    PATIENT = "patient"
    MEDICAL_RECORD = "medical_record"
    QUIZ_RESPONSE = "quiz_response"
    TREATMENT = "treatment"
    PRESCRIPTION = "prescription"
    LAB_RESULT = "lab_result"
    IMAGING = "imaging"
    REPORT = "report"
    MESSAGE = "message"
    USER = "user"
    SYSTEM_CONFIG = "system_config"


class AuditEntry:
    """Structured audit log entry."""

    def __init__(
        self,
        action: AuditAction,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
        timestamp: Optional[datetime] = None,
        patient_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.user_id = user_id
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.patient_id = patient_id
        self.changes = changes or {}
        self.reason = reason
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.session_id = session_id
        self.success = success
        self.error_message = error_message

        # HIPAA compliance tags
        self.compliance_tags = ["hipaa", "audit"]
        if patient_id:
            self.compliance_tags.append("phi_access")

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit entry to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "user_id": self.user_id,
            "patient_id": self.patient_id,
            "changes": self.changes,
            "reason": self.reason,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "success": self.success,
            "error_message": self.error_message,
            "compliance_tags": self.compliance_tags,
        }


class AuditLogger:
    """HIPAA-compliant audit logger."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.retention_days = 2555  # 7 years for HIPAA compliance
        self._buffer: List[AuditEntry] = []
        self._buffer_lock = asyncio.Lock()
        self._buffer_size = 100
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start audit logger background tasks."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush())
        logger.info("Audit logger started")

    async def stop(self):
        """Stop audit logger background tasks."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self._flush_buffer()
        logger.info("Audit logger stopped")

    async def log(
        self,
        action: AuditAction,
        resource_type: ResourceType,
        resource_id: str,
        user_id: str,
        patient_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ):
        """Log an audit event."""
        entry = AuditEntry(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            patient_id=patient_id,
            changes=changes,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            success=success,
            error_message=error_message,
        )

        async with self._buffer_lock:
            self._buffer.append(entry)

            # Flush if buffer is full
            if len(self._buffer) >= self._buffer_size:
                await self._flush_buffer()

        # Also log to application logger
        logger.info(
            f"Audit: {action.value} {resource_type.value} {resource_id}",
            extra={
                "event_type": "audit",
                "audit_action": action.value,
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "user_id": user_id,
                "patient_id": patient_id,
                "success": success,
            },
        )

    async def _periodic_flush(self):
        """Periodically flush audit buffer."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Flush every minute
                await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic audit flush: {e}")

    async def _flush_buffer(self):
        """Flush audit buffer to Redis."""
        async with self._buffer_lock:
            if not self._buffer:
                return

            entries = self._buffer.copy()
            self._buffer.clear()

        if not self.redis:
            return

        try:
            pipeline = self.redis.pipeline()

            for entry in entries:
                # Store in audit log
                audit_key = f"audit:{entry.timestamp.strftime('%Y-%m')}"
                pipeline.rpush(audit_key, json.dumps(entry.to_dict()))
                pipeline.expire(audit_key, self.retention_days * 86400)

                # Store in user-specific audit trail
                if entry.user_id:
                    user_audit_key = f"audit:user:{entry.user_id}"
                    pipeline.rpush(user_audit_key, json.dumps(entry.to_dict()))
                    pipeline.expire(user_audit_key, self.retention_days * 86400)

                # Store in patient-specific audit trail
                if entry.patient_id:
                    patient_audit_key = f"audit:patient:{entry.patient_id}"
                    pipeline.rpush(patient_audit_key, json.dumps(entry.to_dict()))
                    pipeline.expire(patient_audit_key, self.retention_days * 86400)

                # Store in resource-specific audit trail
                resource_audit_key = (
                    f"audit:resource:{entry.resource_type.value}:{entry.resource_id}"
                )
                pipeline.rpush(resource_audit_key, json.dumps(entry.to_dict()))
                pipeline.expire(resource_audit_key, self.retention_days * 86400)

            await pipeline.execute()

            logger.info(f"Flushed {len(entries)} audit entries to Redis")

        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {e}")

    async def get_user_audit_trail(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific user."""
        if not self.redis:
            return []

        try:
            user_audit_key = f"audit:user:{user_id}"
            entries_json = await self.redis.lrange(user_audit_key, 0, -1)

            entries = []
            for entry_json in entries_json:
                entry = json.loads(entry_json)
                entry_time = datetime.fromisoformat(entry["timestamp"])

                if start_time and entry_time < start_time:
                    continue
                if end_time and entry_time > end_time:
                    continue

                entries.append(entry)

            # Sort by timestamp descending
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get user audit trail: {e}")
            return []

    async def get_patient_audit_trail(
        self,
        patient_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific patient (PHI access log)."""
        if not self.redis:
            return []

        try:
            patient_audit_key = f"audit:patient:{patient_id}"
            entries_json = await self.redis.lrange(patient_audit_key, 0, -1)

            entries = []
            for entry_json in entries_json:
                entry = json.loads(entry_json)
                entry_time = datetime.fromisoformat(entry["timestamp"])

                if start_time and entry_time < start_time:
                    continue
                if end_time and entry_time > end_time:
                    continue

                entries.append(entry)

            # Sort by timestamp descending
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get patient audit trail: {e}")
            return []

    async def get_resource_audit_trail(
        self, resource_type: ResourceType, resource_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a specific resource."""
        if not self.redis:
            return []

        try:
            resource_audit_key = f"audit:resource:{resource_type.value}:{resource_id}"
            entries_json = await self.redis.lrange(resource_audit_key, 0, -1)

            entries = []
            for entry_json in entries_json:
                entry = json.loads(entry_json)
                entries.append(entry)

            # Sort by timestamp descending
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get resource audit trail: {e}")
            return []

    async def generate_compliance_report(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Generate HIPAA compliance report for a date range."""
        if not self.redis:
            return {}

        try:
            # Get all audit entries in date range
            months = []
            current = start_date.replace(day=1)
            while current <= end_date:
                months.append(current.strftime("%Y-%m"))
                # Move to next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

            all_entries = []
            for month in months:
                audit_key = f"audit:{month}"
                entries_json = await self.redis.lrange(audit_key, 0, -1)
                for entry_json in entries_json:
                    entry = json.loads(entry_json)
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if start_date <= entry_time <= end_date:
                        all_entries.append(entry)

            # Generate statistics
            total_events = len(all_entries)
            events_by_action = {}
            events_by_resource = {}
            events_by_user = {}
            phi_access_count = 0
            failed_access_count = 0

            for entry in all_entries:
                # Count by action
                action = entry["action"]
                events_by_action[action] = events_by_action.get(action, 0) + 1

                # Count by resource type
                resource_type = entry["resource_type"]
                events_by_resource[resource_type] = (
                    events_by_resource.get(resource_type, 0) + 1
                )

                # Count by user
                user_id = entry["user_id"]
                events_by_user[user_id] = events_by_user.get(user_id, 0) + 1

                # Count PHI access
                if entry.get("patient_id"):
                    phi_access_count += 1

                # Count failed access
                if not entry.get("success", True):
                    failed_access_count += 1

            return {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "total_events": total_events,
                "phi_access_count": phi_access_count,
                "failed_access_count": failed_access_count,
                "events_by_action": events_by_action,
                "events_by_resource": events_by_resource,
                "top_users": sorted(
                    events_by_user.items(), key=lambda x: x[1], reverse=True
                )[:10],
                "compliance_status": "compliant"
                if failed_access_count / max(total_events, 1) < 0.01
                else "review_required",
            }

        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            return {}


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(redis_client: Optional[redis.Redis] = None) -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(redis_client)
    return _audit_logger
