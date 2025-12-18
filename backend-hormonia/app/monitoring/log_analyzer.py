"""
Log Analysis and Search Tools.

Provides advanced log analysis, pattern detection, and search capabilities
with Elasticsearch integration.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import redis.asyncio as redis

from app.utils.logging import get_logger


logger = get_logger(__name__)


class LogQuery:
    """Structured log query builder."""

    def __init__(self):
        self.filters: Dict[str, Any] = {}
        self.time_range: Optional[Dict[str, datetime]] = None
        self.search_text: Optional[str] = None
        self.sort_by: str = "timestamp"
        self.sort_order: str = "desc"
        self.limit: int = 100
        self.offset: int = 0

    def filter_level(self, level: str):
        """Filter by log level."""
        self.filters["level"] = level
        return self

    def filter_category(self, category: str):
        """Filter by log category."""
        self.filters["category"] = category
        return self

    def filter_user(self, user_id: str):
        """Filter by user ID."""
        self.filters["user_id"] = user_id
        return self

    def filter_patient(self, patient_id: str):
        """Filter by patient ID."""
        self.filters["patient_id"] = patient_id
        return self

    def filter_request(self, request_id: str):
        """Filter by request ID."""
        self.filters["request_id"] = request_id
        return self

    def time_range_filter(self, start: datetime, end: datetime):
        """Add time range filter."""
        self.time_range = {"start": start, "end": end}
        return self

    def last_hours(self, hours: int):
        """Filter last N hours."""
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        self.time_range = {"start": start, "end": end}
        return self

    def search(self, text: str):
        """Full-text search."""
        self.search_text = text
        return self

    def sort(self, field: str, order: str = "desc"):
        """Set sort order."""
        self.sort_by = field
        self.sort_order = order
        return self

    def paginate(self, limit: int, offset: int = 0):
        """Set pagination."""
        self.limit = limit
        self.offset = offset
        return self

    def to_elasticsearch_query(self) -> Dict[str, Any]:
        """Convert to Elasticsearch query."""
        query = {"bool": {"must": [], "filter": []}}

        # Add filters
        for field, value in self.filters.items():
            query["bool"]["filter"].append({"term": {field: value}})

        # Add time range
        if self.time_range:
            query["bool"]["filter"].append(
                {
                    "range": {
                        "@timestamp": {
                            "gte": self.time_range["start"].isoformat(),
                            "lte": self.time_range["end"].isoformat(),
                        }
                    }
                }
            )

        # Add text search
        if self.search_text:
            query["bool"]["must"].append(
                {
                    "multi_match": {
                        "query": self.search_text,
                        "fields": ["message", "exception_message", "stack_trace"],
                        "type": "phrase_prefix",
                    }
                }
            )

        return {
            "query": query,
            "sort": [{self.sort_by: {"order": self.sort_order}}],
            "size": self.limit,
            "from": self.offset,
        }


class LogAnalyzer:
    """Advanced log analyzer."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client

    async def analyze_error_patterns(
        self, time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze error patterns in logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_window_hours)

        error_patterns = defaultdict(
            lambda: {
                "count": 0,
                "first_seen": None,
                "last_seen": None,
                "affected_users": set(),
                "affected_patients": set(),
                "error_types": set(),
            }
        )

        if not self.redis:
            return {}

        try:
            # Get error logs from Redis
            pattern = "logs:error:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                logs_json = await self.redis.lrange(key, 0, -1)

                for log_json in logs_json:
                    import json

                    log = json.loads(log_json)

                    log_time = datetime.fromisoformat(log["timestamp"])
                    if not (start_time <= log_time <= end_time):
                        continue

                    # Generate error signature
                    signature = self._generate_error_signature(log)

                    pattern = error_patterns[signature]
                    pattern["count"] += 1

                    if pattern[
                        "first_seen"
                    ] is None or log_time < datetime.fromisoformat(
                        pattern["first_seen"]
                    ):
                        pattern["first_seen"] = log_time.isoformat()

                    if pattern[
                        "last_seen"
                    ] is None or log_time > datetime.fromisoformat(
                        pattern["last_seen"]
                    ):
                        pattern["last_seen"] = log_time.isoformat()

                    if log.get("user_id"):
                        pattern["affected_users"].add(log["user_id"])

                    if log.get("patient_id"):
                        pattern["affected_patients"].add(log["patient_id"])

                    if log.get("exception_type"):
                        pattern["error_types"].add(log["exception_type"])

            # Convert sets to lists for JSON serialization
            result = {}
            for signature, pattern in error_patterns.items():
                result[signature] = {
                    "count": pattern["count"],
                    "first_seen": pattern["first_seen"],
                    "last_seen": pattern["last_seen"],
                    "affected_users": list(pattern["affected_users"]),
                    "affected_patients": list(pattern["affected_patients"]),
                    "error_types": list(pattern["error_types"]),
                    "severity": self._calculate_severity(pattern),
                }

            # Sort by count
            sorted_patterns = dict(
                sorted(result.items(), key=lambda x: x[1]["count"], reverse=True)
            )

            return {
                "time_window_hours": time_window_hours,
                "total_unique_patterns": len(sorted_patterns),
                "patterns": sorted_patterns,
            }

        except Exception as e:
            logger.error(f"Error pattern analysis failed: {e}")
            return {}

    def _generate_error_signature(self, log: Dict[str, Any]) -> str:
        """Generate unique error signature."""
        components = []

        if log.get("exception_type"):
            components.append(log["exception_type"])

        message = log.get("message", "")
        # Extract key parts of error message (first 100 chars)
        if message:
            components.append(message[:100])

        if log.get("api_endpoint"):
            components.append(log["api_endpoint"])

        return ":".join(components)

    def _calculate_severity(self, pattern: Dict[str, Any]) -> str:
        """Calculate error severity based on pattern."""
        count = pattern["count"]
        affected_users = len(pattern["affected_users"])
        affected_patients = len(pattern["affected_patients"])

        if count > 100 or affected_patients > 10:
            return "critical"
        elif count > 50 or affected_users > 5:
            return "high"
        elif count > 10:
            return "medium"
        else:
            return "low"

    async def analyze_performance(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Analyze performance metrics from logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_window_hours)

        api_performance = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0,
                "min_duration": float("inf"),
                "max_duration": 0,
                "status_codes": defaultdict(int),
            }
        )

        db_performance = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0,
                "min_duration": float("inf"),
                "max_duration": 0,
            }
        )

        if not self.redis:
            return {}

        try:
            # Get API logs
            pattern = "logs:api:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                logs_json = await self.redis.lrange(key, 0, -1)

                for log_json in logs_json:
                    import json

                    log = json.loads(log_json)

                    log_time = datetime.fromisoformat(log["timestamp"])
                    if not (start_time <= log_time <= end_time):
                        continue

                    # API performance
                    if log.get("api_endpoint") and log.get("context", {}).get(
                        "duration_ms"
                    ):
                        endpoint = log["api_endpoint"]
                        duration = float(log["context"]["duration_ms"])

                        perf = api_performance[endpoint]
                        perf["count"] += 1
                        perf["total_duration"] += duration
                        perf["min_duration"] = min(perf["min_duration"], duration)
                        perf["max_duration"] = max(perf["max_duration"], duration)

                        if log.get("http_status"):
                            perf["status_codes"][log["http_status"]] += 1

                    # Database performance
                    if log.get("db_table") and log.get("db_duration_ms"):
                        table = log["db_table"]
                        duration = float(log["db_duration_ms"])

                        perf = db_performance[table]
                        perf["count"] += 1
                        perf["total_duration"] += duration
                        perf["min_duration"] = min(perf["min_duration"], duration)
                        perf["max_duration"] = max(perf["max_duration"], duration)

            # Calculate averages
            api_stats = {}
            for endpoint, perf in api_performance.items():
                api_stats[endpoint] = {
                    "count": perf["count"],
                    "avg_duration_ms": perf["total_duration"] / perf["count"],
                    "min_duration_ms": perf["min_duration"],
                    "max_duration_ms": perf["max_duration"],
                    "status_codes": dict(perf["status_codes"]),
                }

            db_stats = {}
            for table, perf in db_performance.items():
                db_stats[table] = {
                    "count": perf["count"],
                    "avg_duration_ms": perf["total_duration"] / perf["count"],
                    "min_duration_ms": perf["min_duration"],
                    "max_duration_ms": perf["max_duration"],
                }

            return {
                "time_window_hours": time_window_hours,
                "api_performance": api_stats,
                "database_performance": db_stats,
                "slowest_apis": sorted(
                    api_stats.items(),
                    key=lambda x: x[1]["avg_duration_ms"],
                    reverse=True,
                )[:10],
                "slowest_db_operations": sorted(
                    db_stats.items(),
                    key=lambda x: x[1]["avg_duration_ms"],
                    reverse=True,
                )[:10],
            }

        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            return {}

    async def analyze_security_events(
        self, time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """Analyze security events from logs."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_window_hours)

        security_stats = {
            "total_events": 0,
            "failed_logins": 0,
            "unauthorized_access": 0,
            "suspicious_ips": set(),
            "events_by_user": defaultdict(int),
            "events_by_type": defaultdict(int),
        }

        if not self.redis:
            return {}

        try:
            pattern = "logs:security:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                logs_json = await self.redis.lrange(key, 0, -1)

                for log_json in logs_json:
                    import json

                    log = json.loads(log_json)

                    log_time = datetime.fromisoformat(log["timestamp"])
                    if not (start_time <= log_time <= end_time):
                        continue

                    security_stats["total_events"] += 1

                    # Count event types
                    event_type = log.get("security_event_type", "unknown")
                    security_stats["events_by_type"][event_type] += 1

                    # Count failed logins
                    if "login" in event_type.lower() and not log.get("success", True):
                        security_stats["failed_logins"] += 1

                    # Count unauthorized access
                    if (
                        "unauthorized" in event_type.lower()
                        or "forbidden" in event_type.lower()
                    ):
                        security_stats["unauthorized_access"] += 1

                    # Track suspicious IPs (multiple failed attempts)
                    if log.get("ip_address") and not log.get("success", True):
                        security_stats["suspicious_ips"].add(log["ip_address"])

                    # Count by user
                    if log.get("user_id"):
                        security_stats["events_by_user"][log["user_id"]] += 1

            return {
                "time_window_hours": time_window_hours,
                "total_events": security_stats["total_events"],
                "failed_logins": security_stats["failed_logins"],
                "unauthorized_access": security_stats["unauthorized_access"],
                "suspicious_ips": list(security_stats["suspicious_ips"]),
                "events_by_type": dict(security_stats["events_by_type"]),
                "top_users": sorted(
                    security_stats["events_by_user"].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10],
                "risk_level": self._calculate_security_risk(security_stats),
            }

        except Exception as e:
            logger.error(f"Security analysis failed: {e}")
            return {}

    def _calculate_security_risk(self, stats: Dict[str, Any]) -> str:
        """Calculate security risk level."""
        failed_logins = stats["failed_logins"]
        unauthorized = stats["unauthorized_access"]
        suspicious_ips = len(stats["suspicious_ips"])

        if failed_logins > 100 or unauthorized > 50 or suspicious_ips > 10:
            return "critical"
        elif failed_logins > 50 or unauthorized > 20 or suspicious_ips > 5:
            return "high"
        elif failed_logins > 10 or unauthorized > 5:
            return "medium"
        else:
            return "low"

    async def correlation_analysis(self, request_id: str) -> Dict[str, Any]:
        """Correlate all logs for a specific request."""
        if not self.redis:
            return {}

        try:
            # Search across all log categories
            correlated_logs = []
            pattern = "logs:*"
            keys = await self.redis.keys(pattern)

            for key in keys:
                logs_json = await self.redis.lrange(key, 0, -1)

                for log_json in logs_json:
                    import json

                    log = json.loads(log_json)

                    if log.get("request_id") == request_id:
                        correlated_logs.append(log)

            # Sort by timestamp
            correlated_logs.sort(key=lambda x: x["timestamp"])

            # Extract request flow
            flow = []
            for log in correlated_logs:
                flow.append(
                    {
                        "timestamp": log["timestamp"],
                        "level": log["level"],
                        "category": log.get("category", "unknown"),
                        "message": log["message"],
                        "api_endpoint": log.get("api_endpoint"),
                        "db_operation": log.get("db_operation"),
                    }
                )

            return {
                "request_id": request_id,
                "total_logs": len(correlated_logs),
                "flow": flow,
                "duration_ms": self._calculate_request_duration(correlated_logs),
                "errors": [
                    log
                    for log in correlated_logs
                    if log["level"] in ["ERROR", "CRITICAL"]
                ],
                "db_queries": [
                    log for log in correlated_logs if log.get("db_operation")
                ],
            }

        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}")
            return {}

    def _calculate_request_duration(
        self, logs: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Calculate total request duration from logs."""
        if not logs:
            return None

        start_time = datetime.fromisoformat(logs[0]["timestamp"])
        end_time = datetime.fromisoformat(logs[-1]["timestamp"])

        duration = (end_time - start_time).total_seconds() * 1000  # Convert to ms
        return duration


# Global log analyzer instance
_log_analyzer: Optional[LogAnalyzer] = None


def get_log_analyzer(redis_client: Optional[redis.Redis] = None) -> LogAnalyzer:
    """Get global log analyzer instance."""
    global _log_analyzer
    if _log_analyzer is None:
        _log_analyzer = LogAnalyzer(redis_client)
    return _log_analyzer
