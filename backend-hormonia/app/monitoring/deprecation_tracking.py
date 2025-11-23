"""
API Deprecation Tracking

Tracks usage of deprecated API endpoints and versions using Prometheus metrics.
Provides visibility into which clients are still using deprecated APIs.

Author: Backend API Developer
Created: 2025-01-16
"""

from prometheus_client import Counter, Gauge, Histogram
from typing import Optional, Dict, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Counter: Total calls to deprecated endpoints
deprecated_endpoint_calls = Counter(
    'api_deprecated_endpoint_calls_total',
    'Total calls to deprecated API endpoints',
    ['version', 'endpoint', 'client_id', 'method']
)

# Counter: API version usage
api_version_usage = Counter(
    'api_version_usage_total',
    'Total API requests by version',
    ['version', 'client_id', 'endpoint']
)

# Gauge: Number of active deprecated endpoints
deprecated_endpoints_active = Gauge(
    'api_deprecated_endpoints_active',
    'Number of currently deprecated endpoints',
    ['version']
)

# Gauge: Days remaining until sunset
api_version_sunset_days = Gauge(
    'api_version_sunset_days_remaining',
    'Days remaining until API version sunset',
    ['version']
)

# Counter: Clients migrated from deprecated versions
api_clients_migrated = Counter(
    'api_clients_migrated_total',
    'Clients migrated from deprecated API versions',
    ['from_version', 'to_version']
)

# Histogram: Response time by API version
api_version_response_time = Histogram(
    'api_version_response_time_seconds',
    'Response time by API version',
    ['version', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
)


# ============================================================================
# Deprecation Tracker
# ============================================================================

class DeprecationTracker:
    """
    Track usage of deprecated API endpoints.

    Features:
    - Track calls to deprecated endpoints
    - Identify clients still using deprecated APIs
    - Generate migration reports
    - Calculate sunset readiness
    """

    def __init__(self):
        self._deprecated_endpoints: Dict[str, Dict] = {}
        self._client_usage: Dict[str, Dict] = {}

    def register_deprecated_endpoint(
        self,
        version: str,
        endpoint: str,
        sunset_date: datetime,
        replacement: Optional[str] = None
    ) -> None:
        """
        Register a deprecated endpoint.

        Args:
            version: API version (e.g., "v2")
            endpoint: Endpoint path (e.g., "/patients")
            sunset_date: When endpoint will be removed
            replacement: Replacement endpoint (optional)
        """
        key = f"{version}:{endpoint}"

        self._deprecated_endpoints[key] = {
            'version': version,
            'endpoint': endpoint,
            'sunset_date': sunset_date,
            'replacement': replacement,
            'registered_at': datetime.now(timezone.utc)
        }

        # Update Prometheus gauge
        deprecated_endpoints_active.labels(version=version).inc()

        logger.info(
            f"Registered deprecated endpoint: {version}{endpoint} "
            f"(sunset: {sunset_date.isoformat()})"
        )

    async def track_call(
        self,
        version: str,
        endpoint: str,
        method: str,
        client_id: Optional[str] = None,
        response_time: Optional[float] = None
    ) -> None:
        """
        Track a call to an API endpoint.

        Args:
            version: API version (e.g., "v2")
            endpoint: Endpoint path (e.g., "/patients")
            method: HTTP method (GET, POST, etc.)
            client_id: Client identifier (optional)
            response_time: Response time in seconds (optional)
        """
        client_id = client_id or 'unknown'

        # Track general API version usage
        api_version_usage.labels(
            version=version,
            client_id=client_id,
            endpoint=endpoint
        ).inc()

        # Track response time
        if response_time is not None:
            api_version_response_time.labels(
                version=version,
                endpoint=endpoint
            ).observe(response_time)

        # If this is a deprecated endpoint, track it specifically
        key = f"{version}:{endpoint}"
        if key in self._deprecated_endpoints:
            deprecated_endpoint_calls.labels(
                version=version,
                endpoint=endpoint,
                client_id=client_id,
                method=method
            ).inc()

            # Track client usage
            if client_id not in self._client_usage:
                self._client_usage[client_id] = {}

            if key not in self._client_usage[client_id]:
                self._client_usage[client_id][key] = {
                    'first_seen': datetime.now(timezone.utc),
                    'last_seen': datetime.now(timezone.utc),
                    'call_count': 0
                }

            self._client_usage[client_id][key]['last_seen'] = datetime.now(timezone.utc)
            self._client_usage[client_id][key]['call_count'] += 1

    def update_sunset_countdown(
        self,
        version: str,
        sunset_date: datetime
    ) -> None:
        """
        Update Prometheus gauge with days remaining until sunset.

        Args:
            version: API version
            sunset_date: Sunset date
        """
        now = datetime.now(timezone.utc)
        days_remaining = max(0, (sunset_date - now).days)

        api_version_sunset_days.labels(version=version).set(days_remaining)

    def get_deprecation_report(self) -> Dict:
        """
        Generate deprecation usage report.

        Returns:
            Report with:
            - Total deprecated endpoints
            - Clients still using deprecated APIs
            - Most used deprecated endpoints
            - Sunset readiness
        """
        now = datetime.now(timezone.utc)

        report = {
            'generated_at': now.isoformat(),
            'deprecated_endpoints': [],
            'clients_at_risk': [],
            'sunset_readiness': {}
        }

        # Analyze each deprecated endpoint
        for key, endpoint_info in self._deprecated_endpoints.items():
            sunset_date = endpoint_info['sunset_date']
            days_remaining = max(0, (sunset_date - now).days)

            # Count clients using this endpoint
            clients_using = [
                client_id
                for client_id, usage in self._client_usage.items()
                if key in usage
            ]

            report['deprecated_endpoints'].append({
                'version': endpoint_info['version'],
                'endpoint': endpoint_info['endpoint'],
                'sunset_date': sunset_date.isoformat(),
                'days_remaining': days_remaining,
                'replacement': endpoint_info['replacement'],
                'clients_using_count': len(clients_using),
                'clients_using': clients_using[:10]  # Top 10
            })

        # Identify clients at risk (still using deprecated APIs)
        for client_id, usage in self._client_usage.items():
            deprecated_usage = []

            for endpoint_key, usage_info in usage.items():
                if endpoint_key in self._deprecated_endpoints:
                    endpoint_info = self._deprecated_endpoints[endpoint_key]
                    deprecated_usage.append({
                        'endpoint': endpoint_info['endpoint'],
                        'version': endpoint_info['version'],
                        'call_count': usage_info['call_count'],
                        'last_seen': usage_info['last_seen'].isoformat()
                    })

            if deprecated_usage:
                report['clients_at_risk'].append({
                    'client_id': client_id,
                    'deprecated_endpoints_used': len(deprecated_usage),
                    'endpoints': deprecated_usage
                })

        # Calculate sunset readiness (% of clients migrated)
        total_clients = len(self._client_usage)
        clients_at_risk = len(report['clients_at_risk'])

        if total_clients > 0:
            migration_percentage = ((total_clients - clients_at_risk) / total_clients) * 100
        else:
            migration_percentage = 100.0

        report['sunset_readiness'] = {
            'total_clients': total_clients,
            'clients_migrated': total_clients - clients_at_risk,
            'clients_at_risk': clients_at_risk,
            'migration_percentage': round(migration_percentage, 2),
            'ready_for_sunset': migration_percentage >= 95.0
        }

        return report

    def get_client_deprecation_status(self, client_id: str) -> Dict:
        """
        Get deprecation status for a specific client.

        Args:
            client_id: Client identifier

        Returns:
            Client's usage of deprecated endpoints
        """
        if client_id not in self._client_usage:
            return {
                'client_id': client_id,
                'status': 'unknown',
                'deprecated_endpoints_used': []
            }

        deprecated_usage = []
        for endpoint_key, usage_info in self._client_usage[client_id].items():
            if endpoint_key in self._deprecated_endpoints:
                endpoint_info = self._deprecated_endpoints[endpoint_key]
                deprecated_usage.append({
                    'endpoint': endpoint_info['endpoint'],
                    'version': endpoint_info['version'],
                    'sunset_date': endpoint_info['sunset_date'].isoformat(),
                    'replacement': endpoint_info['replacement'],
                    'call_count': usage_info['call_count'],
                    'last_seen': usage_info['last_seen'].isoformat()
                })

        status = 'migrated' if not deprecated_usage else 'at_risk'

        return {
            'client_id': client_id,
            'status': status,
            'deprecated_endpoints_used': deprecated_usage
        }

    def record_migration(
        self,
        client_id: str,
        from_version: str,
        to_version: str
    ) -> None:
        """
        Record that a client has migrated to a new API version.

        Args:
            client_id: Client identifier
            from_version: Old API version
            to_version: New API version
        """
        api_clients_migrated.labels(
            from_version=from_version,
            to_version=to_version
        ).inc()

        logger.info(
            f"Client {client_id} migrated from {from_version} to {to_version}"
        )


# Singleton instance
deprecation_tracker = DeprecationTracker()


def get_deprecation_tracker() -> DeprecationTracker:
    """Get the global deprecation tracker instance."""
    return deprecation_tracker
