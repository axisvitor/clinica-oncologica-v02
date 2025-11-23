"""
Security Monitor Service for WhatsApp Access Control.

Comprehensive security monitoring, logging, and alerting system for
unauthorized access attempts, phone blocking, and security analytics.
"""
import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
# from sqlalchemy.orm import
from sqlalchemy import text, func, and_, or_
from sqlalchemy.exc import IntegrityError
import redis.asyncio as redis
import json
import hashlib

from app.core.redis_unified import get_async_redis
from app.core.security_config import get_security_config
from app.models.base import Base
from app.utils.db_retry import with_db_retry

logger = logging.getLogger(__name__)


class SecurityMonitor:
    """
    Security monitoring service for tracking and preventing unauthorized access.

    Features:
    - Unauthorized access attempt tracking
    - Phone number blocking after repeated violations
    - Security event logging and analytics
    - Real-time alerting for suspicious activity
    - Audit trail for compliance
    """

    def __init__(self, db: Any):
        """Initialize security monitor with database session."""
        self.db = db
        self.redis_client = None
        self.security_config = get_security_config()

        # Security thresholds (configurable)
        self.max_attempts_per_hour = 5
        self.max_attempts_per_day = 15
        self.block_duration_hours = 24
        self.alert_threshold = 10  # Alert after 10 attempts in 1 hour

        logger.info("SecurityMonitor initialized")

    async def _get_redis(self) -> redis.Redis:
        """Get Redis client with lazy initialization."""
        if self.redis_client is None:
            self.redis_client = await get_async_redis()
        return self.redis_client

    @with_db_retry(max_retries=3)
    async def log_unauthorized_access(
        self,
        phone: str,
        message_content: str = "",
        source_metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Log unauthorized access attempt with full context.

        Args:
            phone: Phone number that attempted access
            message_content: Content of the message (for analysis)
            source_metadata: Additional metadata (WhatsApp ID, timestamp, etc.)

        Returns:
            UUID of the created audit record
        """
        try:
            audit_id = uuid4()

            # Prepare audit data
            audit_data = {
                "phone": phone,
                "message_content": message_content[:500],  # Limit content length
                "source_metadata": source_metadata or {},
                "timestamp": datetime.utcnow(),
                "risk_score": self._calculate_risk_score(phone, message_content, source_metadata),
                "geolocation": self._extract_geolocation(source_metadata),
                "device_info": self._extract_device_info(source_metadata)
            }

            # Insert audit record
            insert_stmt = text("""
                INSERT INTO security_audit_log (
                    id, event_type, phone_number, message_content, source_metadata,
                    risk_score, ip_address, user_agent, session_id, created_at,
                    additional_data
                )
                VALUES (
                    :id, :event_type, :phone_number, :message_content, :source_metadata,
                    :risk_score, :ip_address, :user_agent, :session_id, :created_at,
                    :additional_data
                )
            """)

            self.db.execute(insert_stmt, {
                "id": str(audit_id),
                "event_type": "unauthorized_whatsapp_access",
                "phone_number": phone,
                "message_content": audit_data["message_content"],
                "source_metadata": json.dumps(audit_data["source_metadata"]),
                "risk_score": audit_data["risk_score"],
                "ip_address": audit_data.get("geolocation", {}).get("ip"),
                "user_agent": audit_data.get("device_info", {}).get("user_agent"),
                "session_id": self._generate_session_id(phone),
                "created_at": audit_data["timestamp"],
                "additional_data": json.dumps({
                    "geolocation": audit_data["geolocation"],
                    "device_info": audit_data["device_info"]
                })
            })

            self.db.commit()

            # Update Redis counters for real-time tracking
            await self._update_redis_counters(phone)

            # Check if alert threshold is reached
            await self._check_alert_threshold(phone, audit_data["risk_score"])

            logger.info(
                f"Logged unauthorized access attempt: {audit_id} "
                f"(phone={phone}, risk_score={audit_data['risk_score']})"
            )

            return audit_id

        except Exception as e:
            logger.error(f"Failed to log unauthorized access for {phone}: {e}", exc_info=True)
            self.db.rollback()
            # Return a fallback UUID to prevent breaking caller logic
            return uuid4()

    @with_db_retry(max_retries=3)
    async def log_authorized_access(
        self,
        phone: str,
        patient_id: UUID,
        source_metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Log successful authorized access for audit trail.

        Args:
            phone: Phone number that accessed successfully
            patient_id: Patient ID that was authorized
            source_metadata: Additional metadata

        Returns:
            UUID of the created audit record
        """
        try:
            audit_id = uuid4()

            # Insert audit record
            insert_stmt = text("""
                INSERT INTO security_audit_log (
                    id, event_type, phone_number, patient_id, source_metadata,
                    risk_score, created_at, additional_data
                )
                VALUES (
                    :id, :event_type, :phone_number, :patient_id, :source_metadata,
                    :risk_score, :created_at, :additional_data
                )
            """)

            self.db.execute(insert_stmt, {
                "id": str(audit_id),
                "event_type": "authorized_whatsapp_access",
                "phone_number": phone,
                "patient_id": str(patient_id),
                "source_metadata": json.dumps(source_metadata or {}),
                "risk_score": 0,  # Authorized access has 0 risk
                "created_at": datetime.utcnow(),
                "additional_data": json.dumps({"access_granted": True})
            })

            self.db.commit()

            # Reset Redis counters for successful access
            await self._reset_redis_counters(phone)

            logger.debug(f"Logged authorized access: {audit_id} (phone={phone}, patient_id={patient_id})")

            return audit_id

        except Exception as e:
            logger.error(f"Failed to log authorized access for {phone}: {e}", exc_info=True)
            self.db.rollback()
            return uuid4()

    async def get_attempt_count(self, phone: str, time_window_hours: int = 1) -> int:
        """
        Get number of unauthorized attempts for a phone number within time window.

        Args:
            phone: Phone number to check
            time_window_hours: Time window in hours (default: 1 hour)

        Returns:
            Number of unauthorized attempts
        """
        try:
            redis_client = await self._get_redis()

            # Try Redis first (fast path)
            cache_key = f"unauthorized_attempts:{phone}:{time_window_hours}h"
            cached_count = await redis_client.get(cache_key)

            if cached_count is not None:
                return int(cached_count)

            # Fallback to database
            since_time = datetime.utcnow() - timedelta(hours=time_window_hours)

            count_stmt = text("""
                SELECT COUNT(*)
                FROM security_audit_log
                WHERE phone_number = :phone
                  AND event_type = 'unauthorized_whatsapp_access'
                  AND created_at > :since_time
            """)

            result = self.db.execute(count_stmt, {
                "phone": phone,
                "since_time": since_time
            }).scalar()

            count = result or 0

            # Cache result for 5 minutes
            await redis_client.setex(cache_key, 300, str(count))

            return count

        except Exception as e:
            logger.error(f"Error getting attempt count for {phone}: {e}")
            return 0

    async def should_block_phone(self, phone: str) -> bool:
        """
        Determine if phone should be blocked based on attempt history.

        Args:
            phone: Phone number to check

        Returns:
            True if phone should be blocked
        """
        try:
            # Check hourly and daily limits
            hourly_attempts = await self.get_attempt_count(phone, 1)
            daily_attempts = await self.get_attempt_count(phone, 24)

            should_block = (
                hourly_attempts >= self.max_attempts_per_hour or
                daily_attempts >= self.max_attempts_per_day
            )

            if should_block:
                logger.warning(
                    f"Phone {phone} should be blocked: "
                    f"hourly_attempts={hourly_attempts}, daily_attempts={daily_attempts}"
                )

            return should_block

        except Exception as e:
            logger.error(f"Error checking block status for {phone}: {e}")
            # Fail safe - don't block on errors
            return False

    async def is_phone_blocked(self, phone: str) -> bool:
        """
        Check if phone number is currently blocked.

        Args:
            phone: Phone number to check

        Returns:
            True if phone is currently blocked
        """
        try:
            redis_client = await self._get_redis()

            # Check Redis for active block
            block_key = f"blocked_phone:{phone}"
            is_blocked = await redis_client.exists(block_key)

            if is_blocked:
                # Get block details for logging
                block_info = await redis_client.hgetall(block_key)
                logger.debug(f"Phone {phone} is blocked: {block_info}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking if phone {phone} is blocked: {e}")
            # Fail safe - don't block on errors
            return False

    async def block_phone(
        self,
        phone: str,
        reason: str,
        duration_hours: int = 24,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Block phone number for specified duration.

        Args:
            phone: Phone number to block
            reason: Reason for blocking
            duration_hours: Block duration in hours
            additional_metadata: Additional context

        Returns:
            True if blocking succeeded
        """
        try:
            redis_client = await self._get_redis()

            # Create block record in Redis
            block_key = f"blocked_phone:{phone}"
            block_data = {
                "phone": phone,
                "reason": reason,
                "blocked_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat(),
                "duration_hours": str(duration_hours),
                "metadata": json.dumps(additional_metadata or {})
            }

            # Set block with expiration
            await redis_client.hset(block_key, mapping=block_data)
            await redis_client.expire(block_key, duration_hours * 3600)

            # Log blocking event to database
            await self._log_block_event(phone, reason, duration_hours, additional_metadata)

            # Send security alert
            await self._send_security_alert(
                alert_type="phone_blocked",
                details={
                    "phone": phone,
                    "reason": reason,
                    "duration_hours": duration_hours
                }
            )

            logger.warning(
                f"Phone {phone} blocked for {duration_hours}h. Reason: {reason}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to block phone {phone}: {e}", exc_info=True)
            return False

    async def unblock_phone(self, phone: str, reason: str = "manual_unblock") -> bool:
        """
        Manually unblock a phone number.

        Args:
            phone: Phone number to unblock
            reason: Reason for unblocking

        Returns:
            True if unblocking succeeded
        """
        try:
            redis_client = await self._get_redis()

            # Remove block from Redis
            block_key = f"blocked_phone:{phone}"
            block_existed = await redis_client.delete(block_key)

            if block_existed:
                # Log unblock event
                await self._log_block_event(phone, f"unblocked: {reason}", 0, {"action": "unblock"})

                logger.info(f"Phone {phone} unblocked. Reason: {reason}")
                return True
            else:
                logger.info(f"Phone {phone} was not blocked")
                return True

        except Exception as e:
            logger.error(f"Failed to unblock phone {phone}: {e}", exc_info=True)
            return False

    async def get_security_stats(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Get security statistics for monitoring dashboard.

        Args:
            time_window_hours: Time window for statistics

        Returns:
            Dictionary with security statistics
        """
        try:
            since_time = datetime.utcnow() - timedelta(hours=time_window_hours)

            # Query database for stats
            stats_stmt = text("""
                SELECT
                    event_type,
                    COUNT(*) as count,
                    AVG(risk_score) as avg_risk_score,
                    MAX(risk_score) as max_risk_score,
                    COUNT(DISTINCT phone_number) as unique_phones
                FROM security_audit_log
                WHERE created_at > :since_time
                GROUP BY event_type
            """)

            results = self.db.execute(stats_stmt, {"since_time": since_time}).fetchall()

            stats = {
                "time_window_hours": time_window_hours,
                "since_time": since_time.isoformat(),
                "events": {},
                "summary": {
                    "total_events": 0,
                    "unauthorized_attempts": 0,
                    "authorized_accesses": 0,
                    "unique_phones": set(),
                    "high_risk_events": 0
                }
            }

            for row in results:
                event_type = row[0]
                stats["events"][event_type] = {
                    "count": row[1],
                    "avg_risk_score": float(row[2]) if row[2] else 0,
                    "max_risk_score": float(row[3]) if row[3] else 0,
                    "unique_phones": row[4]
                }

                # Update summary
                stats["summary"]["total_events"] += row[1]
                if event_type == "unauthorized_whatsapp_access":
                    stats["summary"]["unauthorized_attempts"] += row[1]
                elif event_type == "authorized_whatsapp_access":
                    stats["summary"]["authorized_accesses"] += row[1]

                if row[3] and row[3] > 7:  # High risk threshold
                    stats["summary"]["high_risk_events"] += 1

            # Get currently blocked phones
            redis_client = await self._get_redis()
            blocked_phones = []
            async for key in redis_client.scan_iter(match="blocked_phone:*"):
                phone = key.decode().split(":")[-1]
                block_info = await redis_client.hgetall(key)
                blocked_phones.append({
                    "phone": phone,
                    "blocked_at": block_info.get(b"blocked_at", b"").decode(),
                    "reason": block_info.get(b"reason", b"").decode(),
                    "expires_at": block_info.get(b"expires_at", b"").decode()
                })

            stats["currently_blocked"] = blocked_phones

            return stats

        except Exception as e:
            logger.error(f"Error getting security stats: {e}", exc_info=True)
            return {"error": str(e)}

    # Private helper methods

    def _calculate_risk_score(
        self,
        phone: str,
        message_content: str,
        source_metadata: Optional[Dict[str, Any]]
    ) -> int:
        """Calculate risk score (0-10) for unauthorized access attempt."""
        risk_score = 1  # Base risk for unauthorized access

        # Content-based risk factors
        if message_content:
            suspicious_patterns = [
                "teste", "test", "hack", "admin", "senha", "password",
                "suporte", "support", "ajuda", "help"
            ]

            content_lower = message_content.lower()
            for pattern in suspicious_patterns:
                if pattern in content_lower:
                    risk_score += 2
                    break

            # Long messages might be automated
            if len(message_content) > 100:
                risk_score += 1

        # Time-based risk factors
        current_hour = datetime.utcnow().hour
        if current_hour < 6 or current_hour > 22:  # Outside business hours
            risk_score += 1

        # Metadata-based risk factors
        if source_metadata:
            # Missing common WhatsApp metadata might indicate spoofing
            if not source_metadata.get("pushName"):
                risk_score += 1

            # Very recent timestamps might indicate rapid-fire attempts
            timestamp = source_metadata.get("timestamp")
            if timestamp and isinstance(timestamp, (int, float)):
                msg_time = datetime.fromtimestamp(timestamp / 1000)  # WhatsApp uses milliseconds
                time_diff = datetime.utcnow() - msg_time
                if time_diff.total_seconds() < 5:  # Very recent
                    risk_score += 1

        return min(risk_score, 10)  # Cap at 10

    def _extract_geolocation(self, source_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract geolocation information from metadata."""
        # WhatsApp doesn't provide IP directly, but we can extract what's available
        return {
            "source": "whatsapp",
            "metadata_available": bool(source_metadata)
        }

    def _extract_device_info(self, source_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract device information from metadata."""
        if not source_metadata:
            return {}

        return {
            "push_name": source_metadata.get("pushName"),
            "from_me": source_metadata.get("from_me", False),
            "has_timestamp": "timestamp" in source_metadata
        }

    def _generate_session_id(self, phone: str) -> str:
        """Generate session ID for grouping related events."""
        # Create deterministic session ID based on phone and hour
        current_hour = datetime.utcnow().strftime("%Y%m%d%H")
        session_data = f"{phone}:{current_hour}"
        return hashlib.md5(session_data.encode()).hexdigest()[:16]

    async def _update_redis_counters(self, phone: str) -> None:
        """Update Redis counters for real-time tracking."""
        try:
            redis_client = await self._get_redis()

            # Increment hourly counter
            hourly_key = f"unauthorized_attempts:{phone}:1h"
            await redis_client.incr(hourly_key)
            await redis_client.expire(hourly_key, 3600)  # 1 hour

            # Increment daily counter
            daily_key = f"unauthorized_attempts:{phone}:24h"
            await redis_client.incr(daily_key)
            await redis_client.expire(daily_key, 86400)  # 24 hours

        except Exception as e:
            logger.error(f"Failed to update Redis counters for {phone}: {e}")

    async def _reset_redis_counters(self, phone: str) -> None:
        """Reset Redis counters after successful authorization."""
        try:
            redis_client = await self._get_redis()

            # Reset counters
            hourly_key = f"unauthorized_attempts:{phone}:1h"
            daily_key = f"unauthorized_attempts:{phone}:24h"

            await redis_client.delete(hourly_key, daily_key)

        except Exception as e:
            logger.error(f"Failed to reset Redis counters for {phone}: {e}")

    async def _check_alert_threshold(self, phone: str, risk_score: int) -> None:
        """Check if alert threshold is reached and send alerts."""
        try:
            attempt_count = await self.get_attempt_count(phone, 1)  # Last hour

            if attempt_count >= self.alert_threshold or risk_score >= 8:
                await self._send_security_alert(
                    alert_type="suspicious_activity",
                    details={
                        "phone": phone,
                        "attempt_count": attempt_count,
                        "risk_score": risk_score,
                        "time_window": "1 hour"
                    }
                )

        except Exception as e:
            logger.error(f"Error checking alert threshold for {phone}: {e}")

    async def _log_block_event(
        self,
        phone: str,
        reason: str,
        duration_hours: int,
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Log phone blocking/unblocking event to database."""
        try:
            audit_id = uuid4()

            insert_stmt = text("""
                INSERT INTO security_audit_log (
                    id, event_type, phone_number, created_at, additional_data
                )
                VALUES (
                    :id, :event_type, :phone_number, :created_at, :additional_data
                )
            """)

            self.db.execute(insert_stmt, {
                "id": str(audit_id),
                "event_type": "phone_blocked" if duration_hours > 0 else "phone_unblocked",
                "phone_number": phone,
                "created_at": datetime.utcnow(),
                "additional_data": json.dumps({
                    "reason": reason,
                    "duration_hours": duration_hours,
                    "metadata": metadata or {}
                })
            })

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log block event for {phone}: {e}")
            self.db.rollback()

    async def _send_security_alert(self, alert_type: str, details: Dict[str, Any]) -> None:
        """Send security alert to monitoring systems."""
        try:
            alert_data = {
                "type": alert_type,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details,
                "severity": self._determine_alert_severity(alert_type, details)
            }

            # Log alert
            logger.warning(f"Security alert: {alert_type} - {details}")

            # Here you could integrate with external alerting systems:
            # - Send to Slack/Teams
            # - Send email to security team
            # - Integrate with monitoring tools (DataDog, New Relic, etc.)
            # - Store in dedicated alerts table

            # For now, just log at warning level for monitoring systems to pick up
            logger.warning(f"SECURITY_ALERT: {json.dumps(alert_data)}")

        except Exception as e:
            logger.error(f"Failed to send security alert: {e}")

    def _determine_alert_severity(self, alert_type: str, details: Dict[str, Any]) -> str:
        """Determine alert severity based on type and details."""
        if alert_type == "phone_blocked":
            return "high"
        elif alert_type == "suspicious_activity":
            risk_score = details.get("risk_score", 0)
            if risk_score >= 8:
                return "high"
            elif risk_score >= 5:
                return "medium"
            else:
                return "low"
        else:
            return "medium"
