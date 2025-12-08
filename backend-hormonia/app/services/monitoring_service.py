"""
Monitoring Service
Business logic for system monitoring, consolidating interactions with MonitoringManager.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from fastapi import HTTPException, status

from app.models.user import User, UserRole
from app.monitoring.manager import get_monitoring_manager, MonitoringManager
from app.schemas.v2.enhanced_monitoring import (
    MonitoringHealthResponse,
    SystemMetricsResponse,
    SystemInfoResponse,
    APMGlobalStatsResponse,
    APMEndpointStatsResponse,
    APMEndpointListResponse,
    APMEndpointDetailResponse,
    DatabaseOverviewResponse,
    SlowQueryListResponse,
    SlowQueryResponse,
    TableStatsListResponse,
    TableStatsResponse,
    ConnectionPoolStatsResponse,
    ResourceStatsResponse,
    ResourceHistoricalResponse,
    ResourceTimeSeriesPoint,
    BusinessMetricsSummaryResponse,
    PatientMetricsResponse,
    MetricTypeStatsResponse,
    AnomalyListResponse,
    AnomalyRecord,
    AnomalySummaryResponse,
    DashboardStatusResponse,
    DashboardMetricsSnapshot,
    AlertListResponse,
    AlertRecord,
    AlertSeverity,
    PerformanceOverviewResponse,
    PerformanceScore,
    GrafanaQueryResponse,
    MonitoringConfigResponse,
    StatsResetResponse,
    ServiceActionResponse,
    MetricType
)
from app.api.v2.dependencies import create_cursor, apply_field_selection

logger = logging.getLogger(__name__)

class MonitoringService:
    """Service for monitoring operations."""

    def __init__(self):
        self.manager = get_monitoring_manager()

    def _check_component_availability(self, component_name: str) -> Any:
        """Check if a monitoring component is available."""
        component = getattr(self.manager, component_name, None)
        if not component:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{component_name.replace('_', ' ').title()} not available",
            )
        return component

    def validate_time_range(self, hours: int, max_hours: int = 168) -> None:
        """Validate time range parameters."""
        if hours < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time range must be at least 1 hour",
            )
        if hours > max_hours:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Time range cannot exceed {max_hours} hours (7 days)",
            )

    def calculate_performance_score(
        self,
        apm_stats: Dict[str, Any],
        db_stats: Dict[str, Any],
        resource_stats: Dict[str, Any],
    ) -> PerformanceScore:
        """Calculate overall performance score."""
        score = 100.0
        deductions = []

        # APM performance impact
        error_rate = apm_stats.get("error_rate", 0)
        if error_rate > 5:
            deduction = min(20, error_rate * 2)
            score -= deduction
            deductions.append({"reason": "high_error_rate", "deduction": deduction})

        p95_latency = apm_stats.get("p95", 0)
        if p95_latency > 2000:  # 2 seconds
            deduction = min(15, (p95_latency - 2000) / 100)
            score -= deduction
            deductions.append({"reason": "slow_response_time", "deduction": deduction})

        # Database performance impact
        slow_query_pct = db_stats.get("slow_query_percentage", 0)
        if slow_query_pct > 10:
            deduction = min(15, slow_query_pct)
            score -= deduction
            deductions.append({"reason": "slow_queries", "deduction": deduction})

        # Resource performance impact
        cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
        if cpu_percent > 80:
            deduction = min(15, (cpu_percent - 80) / 2)
            score -= deduction
            deductions.append({"reason": "high_cpu", "deduction": deduction})

        memory_percent = resource_stats.get("memory", {}).get("percent", 0)
        if memory_percent > 85:
            deduction = min(15, (memory_percent - 85) / 2)
            score -= deduction
            deductions.append({"reason": "high_memory", "deduction": deduction})

        # Determine status
        score = max(0, score)
        if score >= 90:
            status_str = "excellent"
        elif score >= 75:
            status_str = "good"
        elif score >= 60:
            status_str = "degraded"
        else:
            status_str = "critical"

        return PerformanceScore(
            score=score,
            status=status_str,
            deductions=deductions,
        )

    async def get_monitoring_health(self) -> MonitoringHealthResponse:
        health_data = self.manager.get_health_status()
        return MonitoringHealthResponse(
            status=health_data.get("status", "unknown"),
            timestamp=datetime.utcnow(),
            components=health_data.get("components", {}),
            uptime_seconds=health_data.get("uptime", 0),
            version=health_data.get("version", "unknown"),
        )

    async def get_metrics_overview(self, fields: Optional[List[str]] = None) -> SystemMetricsResponse:
        metrics = await self.manager.get_system_metrics()
        response_data = {
            "timestamp": datetime.utcnow(),
            "apm": metrics.get("apm", {}),
            "database": metrics.get("database", {}),
            "resources": metrics.get("resources", {}),
            "business": metrics.get("business", {}),
            "health_score": metrics.get("health_score", 100),
        }
        if fields:
            response_data = apply_field_selection(response_data, fields)
        return SystemMetricsResponse(**response_data)

    async def get_system_info(self) -> SystemInfoResponse:
        resource_monitor = self._check_component_availability("resource_monitor")
        info = resource_monitor.get_system_info()
        return SystemInfoResponse(**info)

    async def get_apm_global_stats(self) -> APMGlobalStatsResponse:
        apm_collector = self._check_component_availability("apm_collector")
        stats = apm_collector.get_global_stats()
        return APMGlobalStatsResponse(
            timestamp=datetime.utcnow(),
            total_requests=stats.get("total_requests", 0),
            total_errors=stats.get("total_errors", 0),
            error_rate=stats.get("error_rate", 0.0),
            avg_response_time=stats.get("avg_response_time", 0.0),
            p50=stats.get("p50", 0.0),
            p95=stats.get("p95", 0.0),
            p99=stats.get("p99", 0.0),
            requests_per_second=stats.get("requests_per_second", 0.0),
        )

    async def get_apm_endpoints_stats(self, pagination: Dict, sort_by: str) -> APMEndpointListResponse:
        apm_collector = self._check_component_availability("apm_collector")
        all_stats = apm_collector.get_all_endpoints_stats()

        if sort_by == "error_rate":
            sorted_stats = sorted(all_stats.items(), key=lambda x: x[1].get("error_rate", 0), reverse=True)
        elif sort_by == "avg_latency":
            sorted_stats = sorted(all_stats.items(), key=lambda x: x[1].get("avg_response_time", 0), reverse=True)
        else:
            sorted_stats = sorted(all_stats.items(), key=lambda x: x[1].get("total_requests", 0), reverse=True)

        limit = pagination["limit"]
        cursor_data = pagination["cursor_data"]
        start_idx = cursor_data.get("index", 0) if cursor_data else 0

        paginated_stats = sorted_stats[start_idx : start_idx + limit + 1]
        has_more = len(paginated_stats) > limit

        if has_more:
            paginated_stats = paginated_stats[:limit]
            next_cursor = create_cursor(start_idx + limit)
        else:
            next_cursor = None

        endpoints = [
            APMEndpointStatsResponse(
                endpoint=endpoint_path,
                total_requests=stats.get("total_requests", 0),
                total_errors=stats.get("total_errors", 0),
                error_rate=stats.get("error_rate", 0.0),
                avg_response_time=stats.get("avg_response_time", 0.0),
                p95=stats.get("p95", 0.0),
            )
            for endpoint_path, stats in paginated_stats
        ]

        return APMEndpointListResponse(
            data=endpoints,
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(sorted_stats),
        )

    async def get_apm_endpoint_stats(self, endpoint_path: str) -> APMEndpointDetailResponse:
        apm_collector = self._check_component_availability("apm_collector")
        stats = apm_collector.get_endpoint_stats(endpoint_path)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Endpoint '{endpoint_path}' not found in APM data",
            )

        return APMEndpointDetailResponse(
            endpoint=endpoint_path,
            timestamp=datetime.utcnow(),
            total_requests=stats.get("total_requests", 0),
            total_errors=stats.get("total_errors", 0),
            error_rate=stats.get("error_rate", 0.0),
            avg_response_time=stats.get("avg_response_time", 0.0),
            min_response_time=stats.get("min_response_time", 0.0),
            max_response_time=stats.get("max_response_time", 0.0),
            p50=stats.get("p50", 0.0),
            p95=stats.get("p95", 0.0),
            p99=stats.get("p99", 0.0),
            recent_errors=stats.get("recent_errors", []),
            status_code_distribution=stats.get("status_codes", {}),
        )

    async def get_database_overview(self) -> DatabaseOverviewResponse:
        db_monitor = self._check_component_availability("db_monitor")
        query_stats = db_monitor.get_query_stats()
        pool_stats = db_monitor.get_connection_pool_stats()

        return DatabaseOverviewResponse(
            timestamp=datetime.utcnow(),
            query_statistics=query_stats,
            connection_pool=ConnectionPoolStatsResponse(**pool_stats),
        )

    async def get_slow_queries(self, pagination: Dict, min_duration_ms: float) -> SlowQueryListResponse:
        db_monitor = self._check_component_availability("db_monitor")
        limit = pagination["limit"]
        all_slow_queries = db_monitor.get_slow_queries(limit=1000)
        filtered_queries = [q for q in all_slow_queries if q.get("duration_ms", 0) >= min_duration_ms]

        cursor_data = pagination["cursor_data"]
        start_idx = cursor_data.get("index", 0) if cursor_data else 0

        paginated = filtered_queries[start_idx : start_idx + limit + 1]
        has_more = len(paginated) > limit

        if has_more:
            paginated = paginated[:limit]
            next_cursor = create_cursor(start_idx + limit)
        else:
            next_cursor = None

        queries = [
            SlowQueryResponse(
                query=q.get("query", ""),
                duration_ms=q.get("duration_ms", 0.0),
                timestamp=q.get("timestamp", datetime.utcnow()),
                table=q.get("table"),
                rows_examined=q.get("rows_examined"),
            )
            for q in paginated
        ]

        return SlowQueryListResponse(
            data=queries,
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(filtered_queries),
        )

    async def get_table_stats(self) -> TableStatsListResponse:
        db_monitor = self._check_component_availability("db_monitor")
        table_stats_dict = db_monitor.get_table_stats()

        table_stats = [
            TableStatsResponse(
                table=table_name,
                query_count=stats.get("query_count", 0),
                avg_duration_ms=stats.get("avg_duration_ms", 0.0),
                total_duration_ms=stats.get("total_duration_ms", 0.0),
                slow_query_count=stats.get("slow_query_count", 0),
            )
            for table_name, stats in table_stats_dict.items()
        ]
        table_stats.sort(key=lambda x: x.query_count, reverse=True)

        return TableStatsListResponse(
            data=table_stats,
            timestamp=datetime.utcnow(),
            total_tables=len(table_stats),
        )

    async def get_current_resources(self) -> ResourceStatsResponse:
        resource_monitor = self._check_component_availability("resource_monitor")
        stats = resource_monitor.get_current_stats()
        return ResourceStatsResponse(
            timestamp=datetime.utcnow(),
            cpu=stats.get("cpu", {}),
            memory=stats.get("memory", {}),
            disk=stats.get("disk", {}),
            network=stats.get("network", {}),
        )

    async def get_historical_resources(self, minutes: int) -> ResourceHistoricalResponse:
        resource_monitor = self._check_component_availability("resource_monitor")
        historical_data = resource_monitor.get_historical_stats(minutes)

        time_series = [
            ResourceTimeSeriesPoint(
                timestamp=point.get("timestamp", datetime.utcnow()),
                cpu_percent=point.get("cpu", {}).get("percent", 0.0),
                memory_percent=point.get("memory", {}).get("percent", 0.0),
                disk_percent=point.get("disk", {}).get("percent", 0.0),
                network_bytes_sent=point.get("network", {}).get("bytes_sent", 0),
                network_bytes_recv=point.get("network", {}).get("bytes_recv", 0),
            )
            for point in historical_data.get("data_points", [])
        ]

        return ResourceHistoricalResponse(
            time_range_minutes=minutes,
            data_points=time_series,
            summary=historical_data.get("summary", {}),
        )

    async def get_business_metrics_summary(self, hours: int) -> BusinessMetricsSummaryResponse:
        self.validate_time_range(hours)
        business_metrics = self._check_component_availability("business_metrics")
        summary = business_metrics.get_all_metrics_summary(hours)
        return BusinessMetricsSummaryResponse(
            time_range_hours=hours,
            timestamp=datetime.utcnow(),
            metrics=summary,
        )

    async def get_patient_metrics(self, patient_id: str, hours: int) -> PatientMetricsResponse:
        self.validate_time_range(hours)
        business_metrics = self._check_component_availability("business_metrics")
        metrics = business_metrics.get_patient_metrics(patient_id, hours)
        return PatientMetricsResponse(
            patient_id=patient_id,
            time_range_hours=hours,
            timestamp=datetime.utcnow(),
            metrics=metrics,
        )

    async def get_business_metric_stats(self, metric_type: MetricType, hours: int) -> MetricTypeStatsResponse:
        self.validate_time_range(hours)
        business_metrics = self._check_component_availability("business_metrics")
        stats = business_metrics.get_metric_stats(metric_type, hours)
        return MetricTypeStatsResponse(
            metric_type=metric_type,
            time_range_hours=hours,
            timestamp=datetime.utcnow(),
            statistics=stats,
        )

    async def get_recent_anomalies(self, hours: int, severity: Optional[str], metric: Optional[str], pagination: Dict) -> AnomalyListResponse:
        self.validate_time_range(hours)
        anomaly_detector = self._check_component_availability("anomaly_detector")
        anomalies_data = anomaly_detector.get_recent_anomalies(hours, severity, metric)

        limit = pagination["limit"]
        cursor_data = pagination["cursor_data"]
        start_idx = cursor_data.get("index", 0) if cursor_data else 0

        paginated = anomalies_data[start_idx : start_idx + limit + 1]
        has_more = len(paginated) > limit

        if has_more:
            paginated = paginated[:limit]
            next_cursor = create_cursor(start_idx + limit)
        else:
            next_cursor = None

        anomalies = [
            AnomalyRecord(
                timestamp=a.get("timestamp", datetime.utcnow()),
                metric=a.get("metric", ""),
                value=a.get("value", 0.0),
                expected_value=a.get("expected_value", 0.0),
                severity=a.get("severity", "medium"),
                description=a.get("description", ""),
            )
            for a in paginated
        ]

        return AnomalyListResponse(
            data=anomalies,
            next_cursor=next_cursor,
            has_more=has_more,
            total=len(anomalies_data),
        )

    async def get_anomalies_summary(self, hours: int) -> AnomalySummaryResponse:
        self.validate_time_range(hours)
        anomaly_detector = self._check_component_availability("anomaly_detector")
        summary = anomaly_detector.get_anomaly_summary(hours)
        return AnomalySummaryResponse(
            time_range_hours=hours,
            timestamp=datetime.utcnow(),
            total_anomalies=summary.get("total", 0),
            by_severity=summary.get("by_severity", {}),
            by_metric=summary.get("by_metric", {}),
        )

    async def get_dashboard_status(self) -> DashboardStatusResponse:
        dashboard = self._check_component_availability("dashboard")
        status_data = dashboard.get_dashboard_status()
        return DashboardStatusResponse(
            timestamp=datetime.utcnow(),
            active_connections=status_data.get("active_connections", 0),
            metrics_snapshot=DashboardMetricsSnapshot(**status_data.get("metrics", {})),
        )

    async def get_active_alerts(self, severity: Optional[AlertSeverity]) -> AlertListResponse:
        alerts = []
        
        if self.manager.apm_collector:
            apm_stats = self.manager.apm_collector.get_global_stats()
            error_rate = apm_stats.get("error_rate", 0)
            if error_rate > 5:
                severity_level = "critical" if error_rate > 10 else "high" if error_rate > 7 else "medium"
                alerts.append(AlertRecord(type="apm", severity=severity_level, message=f"High error rate: {error_rate:.1f}%", value=error_rate, threshold=5.0, timestamp=datetime.utcnow()))

        if self.manager.resource_monitor:
            resource_stats = self.manager.resource_monitor.get_current_stats()
            cpu_percent = resource_stats.get("cpu", {}).get("percent", 0)
            memory_percent = resource_stats.get("memory", {}).get("percent", 0)

            if cpu_percent > 80:
                severity_level = "critical" if cpu_percent > 95 else "high"
                alerts.append(AlertRecord(type="resource", severity=severity_level, message=f"High CPU usage: {cpu_percent:.1f}%", value=cpu_percent, threshold=80.0, timestamp=datetime.utcnow()))

            if memory_percent > 85:
                severity_level = "critical" if memory_percent > 95 else "high"
                alerts.append(AlertRecord(type="resource", severity=severity_level, message=f"High memory usage: {memory_percent:.1f}%", value=memory_percent, threshold=85.0, timestamp=datetime.utcnow()))

        if severity:
            alerts = [a for a in alerts if a.severity == severity.value]

        return AlertListResponse(alerts=alerts, count=len(alerts), timestamp=datetime.utcnow())

    async def get_performance_overview(self) -> PerformanceOverviewResponse:
        apm_stats = self.manager.apm_collector.get_global_stats() if self.manager.apm_collector else {}
        db_stats = self.manager.db_monitor.get_query_stats() if self.manager.db_monitor else {}
        resource_stats = self.manager.resource_monitor.get_current_stats() if self.manager.resource_monitor else {}

        perf_score = self.calculate_performance_score(apm_stats, db_stats, resource_stats)

        return PerformanceOverviewResponse(
            timestamp=datetime.utcnow(),
            performance_score=perf_score,
            apm=apm_stats,
            database=db_stats,
            resources=resource_stats,
            system_health=self.manager.get_health_status(),
        )

    async def query_grafana_metrics(self, request_data: Any) -> GrafanaQueryResponse:
        metrics_exporter = self._check_component_availability("metrics_exporter")
        result = await metrics_exporter.query_grafana_metrics(
            targets=request_data.targets,
            from_time=request_data.range.from_time,
            to_time=request_data.range.to_time,
            max_data_points=request_data.max_data_points,
        )
        return GrafanaQueryResponse(**result)

    async def reset_monitoring_stats(self, user_id: str) -> StatsResetResponse:
        await self.manager.reset_all_stats()
        logger.warning(f"All monitoring statistics reset by user {user_id}")
        return StatsResetResponse(
            message="All monitoring statistics have been reset",
            timestamp=datetime.utcnow(),
            reset_by=str(user_id),
        )

    async def start_monitoring_services(self, user_id: str) -> ServiceActionResponse:
        if self.manager._started:
            return ServiceActionResponse(success=True, message="Monitoring services are already running", timestamp=datetime.utcnow())
        
        await self.manager.start()
        logger.info(f"Monitoring services started by user {user_id}")
        return ServiceActionResponse(success=True, message="Monitoring services started successfully", timestamp=datetime.utcnow())

    async def stop_monitoring_services(self, user_id: str) -> ServiceActionResponse:
        if not self.manager._started:
            return ServiceActionResponse(success=True, message="Monitoring services are not running", timestamp=datetime.utcnow())
        
        await self.manager.stop()
        logger.info(f"Monitoring services stopped by user {user_id}")
        return ServiceActionResponse(success=True, message="Monitoring services stopped successfully", timestamp=datetime.utcnow())
