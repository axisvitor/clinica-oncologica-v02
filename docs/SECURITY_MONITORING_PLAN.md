# WhatsApp Security Monitoring and Alerting Plan

## Overview
Comprehensive security monitoring system for WhatsApp patient authorization with real-time alerting, dashboard integration, and automated threat detection.

## Monitoring Architecture

### 1. Real-Time Security Dashboard

```python
# File: app/api/v1/security.py
"""
Security monitoring endpoints for WhatsApp authorization events.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.middleware.admin_permissions import require_admin
from app.schemas.security import SecurityDashboardResponse, SecurityEvent

router = APIRouter()

@router.get("/security/whatsapp/dashboard", response_model=SecurityDashboardResponse)
async def get_security_dashboard(
    hours: int = Query(24, description="Hours to look back"),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get WhatsApp security dashboard data."""

    since = datetime.utcnow() - timedelta(hours=hours)

    # Get security statistics
    stats = await _get_security_stats(db, since)

    # Get recent security events
    events = await _get_recent_security_events(db, since, limit=100)

    # Get threat analysis
    threats = await _analyze_security_threats(db, since)

    return SecurityDashboardResponse(
        timeframe_hours=hours,
        statistics=stats,
        recent_events=events,
        threat_analysis=threats,
        generated_at=datetime.utcnow()
    )

@router.get("/security/whatsapp/events", response_model=List[SecurityEvent])
async def get_security_events(
    event_type: Optional[str] = Query(None),
    phone_number: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get filtered security events."""

    query = """
        SELECT
            id, phone_number, patient_id, event_type, webhook_path,
            metadata, ip_address, user_agent, created_at
        FROM whatsapp_security_events
        WHERE 1=1
    """

    params = {}

    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type

    if phone_number:
        query += " AND phone_number = :phone_number"
        params["phone_number"] = phone_number

    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    params.update({"limit": limit, "offset": offset})

    result = db.execute(text(query), params)

    return [SecurityEvent.from_db_row(row) for row in result.fetchall()]

async def _get_security_stats(db: Session, since: datetime) -> Dict[str, Any]:
    """Get security statistics for dashboard."""

    stats_query = text("""
        SELECT
            event_type,
            COUNT(*) as count,
            COUNT(DISTINCT phone_number) as unique_phones,
            MIN(created_at) as first_seen,
            MAX(created_at) as last_seen
        FROM whatsapp_security_events
        WHERE created_at >= :since
        GROUP BY event_type
        ORDER BY count DESC
    """)

    result = db.execute(stats_query, {"since": since})

    stats = {
        "total_events": 0,
        "authorized_events": 0,
        "unauthorized_events": 0,
        "blocked_phones": set(),
        "event_breakdown": {}
    }

    for row in result:
        event_type = row.event_type
        count = row.count
        unique_phones = row.unique_phones

        stats["total_events"] += count
        stats["event_breakdown"][event_type] = {
            "count": count,
            "unique_phones": unique_phones,
            "first_seen": row.first_seen,
            "last_seen": row.last_seen
        }

        if event_type == "AUTHORIZED":
            stats["authorized_events"] += count
        elif event_type in ["UNAUTHORIZED_PHONE", "RATE_LIMITED"]:
            stats["unauthorized_events"] += count
            # Get blocked phone numbers for this event type
            blocked_phones_query = text("""
                SELECT DISTINCT phone_number
                FROM whatsapp_security_events
                WHERE event_type = :event_type AND created_at >= :since
            """)
            blocked_result = db.execute(blocked_phones_query, {
                "event_type": event_type,
                "since": since
            })
            stats["blocked_phones"].update([row[0] for row in blocked_result])

    stats["blocked_phones"] = len(stats["blocked_phones"])
    return stats

async def _analyze_security_threats(db: Session, since: datetime) -> List[Dict[str, Any]]:
    """Analyze security threats and patterns."""

    # Identify phones with multiple unauthorized attempts
    threat_query = text("""
        SELECT
            phone_number,
            COUNT(*) as attempt_count,
            array_agg(DISTINCT event_type) as event_types,
            MIN(created_at) as first_attempt,
            MAX(created_at) as last_attempt,
            array_agg(DISTINCT ip_address) as ip_addresses
        FROM whatsapp_security_events
        WHERE created_at >= :since
          AND event_type IN ('UNAUTHORIZED_PHONE', 'RATE_LIMITED', 'SUSPICIOUS_ACTIVITY')
        GROUP BY phone_number
        HAVING COUNT(*) >= 3
        ORDER BY attempt_count DESC, last_attempt DESC
        LIMIT 20
    """)

    result = db.execute(threat_query, {"since": since})

    threats = []
    for row in result:
        threat_level = "HIGH" if row.attempt_count >= 10 else "MEDIUM"

        threats.append({
            "phone_number": row.phone_number,
            "threat_level": threat_level,
            "attempt_count": row.attempt_count,
            "event_types": row.event_types,
            "first_attempt": row.first_attempt,
            "last_attempt": row.last_attempt,
            "ip_addresses": row.ip_addresses,
            "description": f"Phone number with {row.attempt_count} unauthorized attempts"
        })

    return threats
```

### 2. Real-Time Alerting System

```python
# File: app/services/security_alerting.py
"""
Real-time security alerting system for WhatsApp threats.
"""
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.slack import SlackClient
from app.integrations.email import EmailService

logger = logging.getLogger(__name__)

class SecurityAlertingService:
    """Service for real-time security threat alerting."""

    def __init__(self):
        self.slack_client = SlackClient() if settings.SLACK_WEBHOOK_URL else None
        self.email_service = EmailService() if settings.EMAIL_ENABLED else None

        # Alert thresholds
        self.unauthorized_threshold = 5  # alerts after 5 unauthorized attempts
        self.rate_limit_threshold = 3   # alerts after 3 rate limit hits
        self.time_window = 300          # 5 minutes

        # Alert cooldown to prevent spam
        self.alert_cooldown = {}  # phone -> last_alert_time
        self.cooldown_minutes = 15

    async def process_security_event(
        self,
        event_type: str,
        phone_number: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Process security event and trigger alerts if needed."""

        # Check if we should alert for this event
        should_alert = await self._should_alert(event_type, phone_number, metadata)

        if should_alert:
            await self._send_security_alert(event_type, phone_number, metadata)

    async def _should_alert(
        self,
        event_type: str,
        phone_number: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Determine if we should send an alert for this event."""

        # Check cooldown
        if self._is_in_cooldown(phone_number):
            return False

        # Alert conditions
        alert_conditions = {
            "UNAUTHORIZED_PHONE": lambda: self._check_unauthorized_pattern(phone_number),
            "RATE_LIMITED": lambda: self._check_rate_limit_pattern(phone_number),
            "SUSPICIOUS_ACTIVITY": lambda: True,  # Always alert
            "SECURITY_BREACH": lambda: True,      # Always alert
        }

        condition_check = alert_conditions.get(event_type)
        if condition_check:
            return await condition_check()

        return False

    def _is_in_cooldown(self, phone_number: str) -> bool:
        """Check if phone number is in alert cooldown period."""
        last_alert = self.alert_cooldown.get(phone_number)
        if not last_alert:
            return False

        cooldown_until = last_alert + timedelta(minutes=self.cooldown_minutes)
        return datetime.utcnow() < cooldown_until

    async def _check_unauthorized_pattern(self, phone_number: str) -> bool:
        """Check if unauthorized attempts exceed threshold."""
        # Count recent unauthorized attempts for this phone
        # This would query the database for recent events
        # Return True if threshold exceeded
        return True  # Simplified for example

    async def _send_security_alert(
        self,
        event_type: str,
        phone_number: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Send security alert via configured channels."""

        # Create alert message
        alert_data = {
            "alert_type": "whatsapp_security",
            "severity": self._get_alert_severity(event_type),
            "event_type": event_type,
            "phone_number": phone_number,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata
        }

        # Send to Slack
        if self.slack_client:
            await self._send_slack_alert(alert_data)

        # Send email alert
        if self.email_service:
            await self._send_email_alert(alert_data)

        # Update cooldown
        self.alert_cooldown[phone_number] = datetime.utcnow()

        logger.warning(f"Security alert sent: {event_type} for {phone_number}")

    async def _send_slack_alert(self, alert_data: Dict[str, Any]) -> None:
        """Send alert to Slack channel."""

        severity_emoji = {
            "high": "🚨",
            "medium": "⚠️",
            "low": "ℹ️"
        }

        emoji = severity_emoji.get(alert_data["severity"], "⚠️")

        message = f"""
{emoji} **WhatsApp Security Alert**

**Event Type:** {alert_data["event_type"]}
**Phone Number:** {alert_data["phone_number"]}
**Severity:** {alert_data["severity"].upper()}
**Time:** {alert_data["timestamp"]}

**Details:**
{self._format_metadata(alert_data["metadata"])}

*Hormonia Clinic Security System*
        """.strip()

        await self.slack_client.send_message(
            channel=settings.SECURITY_SLACK_CHANNEL,
            message=message
        )

    def _get_alert_severity(self, event_type: str) -> str:
        """Get alert severity level for event type."""
        severity_map = {
            "UNAUTHORIZED_PHONE": "medium",
            "RATE_LIMITED": "medium",
            "SUSPICIOUS_ACTIVITY": "high",
            "SECURITY_BREACH": "high",
            "PHONE_NORMALIZATION_FAILED": "low"
        }
        return severity_map.get(event_type, "medium")

    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata for alert display."""
        formatted = []
        for key, value in metadata.items():
            if key in ["ip_address", "user_agent", "attempt_count", "block_reason"]:
                formatted.append(f"• {key.replace('_', ' ').title()}: {value}")
        return "\n".join(formatted) if formatted else "No additional details"
```

### 3. Automated Threat Detection

```python
# File: app/services/threat_detection.py
"""
Automated threat detection for WhatsApp security events.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ThreatDetectionService:
    """Service for automated WhatsApp threat detection and response."""

    def __init__(self, db: Session):
        self.db = db

    async def analyze_phone_behavior(self, phone_number: str) -> Dict[str, Any]:
        """Analyze behavior pattern for a specific phone number."""

        # Get recent activity (last 24 hours)
        since = datetime.utcnow() - timedelta(hours=24)

        activity_query = text("""
            SELECT
                event_type,
                COUNT(*) as count,
                array_agg(created_at ORDER BY created_at) as timestamps,
                array_agg(DISTINCT ip_address) as ip_addresses,
                array_agg(DISTINCT webhook_path) as endpoints
            FROM whatsapp_security_events
            WHERE phone_number = :phone_number AND created_at >= :since
            GROUP BY event_type
        """)

        result = self.db.execute(activity_query, {
            "phone_number": phone_number,
            "since": since
        })

        behavior_analysis = {
            "phone_number": phone_number,
            "analysis_period": "24h",
            "threat_score": 0,
            "threat_level": "LOW",
            "patterns": [],
            "recommendations": []
        }

        for row in result:
            event_type = row.event_type
            count = row.count
            timestamps = row.timestamps

            # Analyze patterns
            if event_type == "UNAUTHORIZED_PHONE" and count > 5:
                behavior_analysis["threat_score"] += 30
                behavior_analysis["patterns"].append({
                    "type": "excessive_unauthorized_attempts",
                    "count": count,
                    "severity": "HIGH"
                })

            if event_type == "RATE_LIMITED" and count > 3:
                behavior_analysis["threat_score"] += 20
                behavior_analysis["patterns"].append({
                    "type": "rate_limiting_triggered",
                    "count": count,
                    "severity": "MEDIUM"
                })

            # Check for rapid-fire attempts
            if len(timestamps) > 1:
                time_diffs = [
                    (timestamps[i+1] - timestamps[i]).total_seconds()
                    for i in range(len(timestamps)-1)
                ]
                avg_interval = sum(time_diffs) / len(time_diffs)

                if avg_interval < 30:  # Less than 30 seconds between attempts
                    behavior_analysis["threat_score"] += 25
                    behavior_analysis["patterns"].append({
                        "type": "rapid_fire_attempts",
                        "avg_interval_seconds": avg_interval,
                        "severity": "HIGH"
                    })

        # Determine threat level
        if behavior_analysis["threat_score"] >= 50:
            behavior_analysis["threat_level"] = "HIGH"
            behavior_analysis["recommendations"].append("Consider blocking this phone number")
        elif behavior_analysis["threat_score"] >= 25:
            behavior_analysis["threat_level"] = "MEDIUM"
            behavior_analysis["recommendations"].append("Monitor closely for escalation")

        return behavior_analysis

    async def detect_distributed_attacks(self) -> List[Dict[str, Any]]:
        """Detect potential distributed attacks across multiple phone numbers."""

        # Look for patterns in the last hour
        since = datetime.utcnow() - timedelta(hours=1)

        # Check for multiple phones from same IP
        ip_analysis_query = text("""
            SELECT
                ip_address,
                COUNT(DISTINCT phone_number) as unique_phones,
                COUNT(*) as total_events,
                array_agg(DISTINCT phone_number) as phone_numbers,
                array_agg(DISTINCT event_type) as event_types
            FROM whatsapp_security_events
            WHERE created_at >= :since
              AND ip_address IS NOT NULL
              AND event_type IN ('UNAUTHORIZED_PHONE', 'RATE_LIMITED')
            GROUP BY ip_address
            HAVING COUNT(DISTINCT phone_number) >= 3
            ORDER BY unique_phones DESC
        """)

        result = self.db.execute(ip_analysis_query, {"since": since})

        distributed_threats = []

        for row in result:
            threat = {
                "type": "distributed_attack",
                "source_ip": row.ip_address,
                "unique_phones": row.unique_phones,
                "total_events": row.total_events,
                "phone_numbers": row.phone_numbers,
                "event_types": row.event_types,
                "severity": "HIGH" if row.unique_phones >= 5 else "MEDIUM",
                "detected_at": datetime.utcnow(),
                "recommendations": [
                    f"Consider blocking IP address {row.ip_address}",
                    "Investigate potential bot/automated attack"
                ]
            }

            distributed_threats.append(threat)

        return distributed_threats

    async def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""

        # Get data for last 7 days
        since = datetime.utcnow() - timedelta(days=7)

        report = {
            "report_period": "7_days",
            "generated_at": datetime.utcnow(),
            "summary": await self._get_security_summary(since),
            "top_threats": await self._get_top_threats(since),
            "trend_analysis": await self._get_trend_analysis(since),
            "recommendations": []
        }

        # Generate recommendations based on data
        if report["summary"]["unauthorized_events"] > 100:
            report["recommendations"].append(
                "High volume of unauthorized access attempts detected. "
                "Consider implementing additional rate limiting."
            )

        if len(report["top_threats"]) > 10:
            report["recommendations"].append(
                "Multiple threat sources identified. "
                "Consider implementing IP-based blocking."
            )

        return report

    async def _get_security_summary(self, since: datetime) -> Dict[str, Any]:
        """Get security summary statistics."""

        summary_query = text("""
            SELECT
                COUNT(*) as total_events,
                COUNT(CASE WHEN event_type = 'AUTHORIZED' THEN 1 END) as authorized_events,
                COUNT(CASE WHEN event_type != 'AUTHORIZED' THEN 1 END) as unauthorized_events,
                COUNT(DISTINCT phone_number) as unique_phones,
                COUNT(DISTINCT ip_address) as unique_ips
            FROM whatsapp_security_events
            WHERE created_at >= :since
        """)

        result = self.db.execute(summary_query, {"since": since}).fetchone()

        return {
            "total_events": result.total_events,
            "authorized_events": result.authorized_events,
            "unauthorized_events": result.unauthorized_events,
            "unique_phones": result.unique_phones,
            "unique_ips": result.unique_ips,
            "success_rate": (result.authorized_events / result.total_events * 100)
                           if result.total_events > 0 else 0
        }
```

## Implementation Priority

### Phase 1: Core Monitoring (Week 1)
1. **Security Events Database** - Create tables and basic logging
2. **Dashboard API** - Basic security statistics endpoint
3. **Event Processing** - Integrate with enhanced webhook processor

### Phase 2: Real-Time Alerting (Week 2)
1. **Slack Integration** - Real-time alerts to security channel
2. **Email Alerts** - Critical security event notifications
3. **Alert Thresholds** - Configurable alerting rules

### Phase 3: Threat Detection (Week 3)
1. **Behavior Analysis** - Automated phone number threat scoring
2. **Distributed Attack Detection** - Multi-phone/IP pattern detection
3. **Security Reports** - Automated daily/weekly security reports

### Phase 4: Advanced Features (Week 4)
1. **ML-Based Detection** - Machine learning threat detection
2. **Automated Response** - Automatic blocking of high-threat sources
3. **Integration Dashboard** - Full security monitoring UI

## Monitoring Metrics

### Key Performance Indicators (KPIs):
- **Authorization Success Rate** - % of authorized vs unauthorized attempts
- **Threat Detection Accuracy** - False positive/negative rates
- **Response Time** - Time from threat detection to alert
- **Block Effectiveness** - Reduction in repeat unauthorized attempts

### Security Metrics:
- **Unauthorized Attempts per Hour** - Trend of attack volume
- **Unique Threat Sources** - Number of different attacking phones/IPs
- **Geographic Distribution** - Location analysis of threats
- **Attack Pattern Analysis** - Types and sophistication of attacks