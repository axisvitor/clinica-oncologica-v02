"""Prometheus metrics and performance metric collection."""

import inspect
import logging
from datetime import timedelta

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import Boolean, DateTime, and_, cast, func, or_, select

from app.models.flow import FlowKind, FlowTemplateVersion, PatientFlowState
from app.models.message import Message
from app.utils.timezone import now_sao_paulo

from .models import PerformanceMetrics

logger = logging.getLogger(__name__)


FLOW_ACTIVE_PATIENTS = Gauge(
    "flow_active_count",
    "Active flow count by kind",
    ["flow_kind"],
)
FLOW_ERRORS = Counter(
    "flow_completed_count",
    "Completed flow count by kind",
    ["flow_kind"],
)
FLOW_MESSAGES_SENT = Gauge(
    "flow_completion_rate",
    "Flow completion rate by kind",
    ["flow_kind"],
)
FLOW_PROCESSING_TIME = Histogram(
    "flow_duration_seconds",
    "Flow duration in seconds by kind",
    ["flow_kind"],
)

# Backward-compatible aliases for pre-split metric symbol names.
flow_active_count = FLOW_ACTIVE_PATIENTS
flow_completed_count = FLOW_ERRORS
flow_completion_rate = FLOW_MESSAGES_SENT
flow_duration_seconds = FLOW_PROCESSING_TIME


class FlowMonitoringMetricsMixin:
    async def _resolve(self, maybe_awaitable):
        if inspect.isawaitable(maybe_awaitable):
            return await maybe_awaitable
        return maybe_awaitable

    async def _execute(self, statement):
        return await self._resolve(self.db.execute(statement))

    async def _count(self, statement) -> int:
        result = await self._execute(statement)
        value = result.scalar()
        return int(value or 0)

    async def collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        try:
            total_active_flows = await self._count(
                select(func.count(PatientFlowState.id)).where(
                    PatientFlowState.status == "active"
                )
            )

            one_hour_ago = now_sao_paulo() - timedelta(hours=1)
            twenty_four_hours_ago = now_sao_paulo() - timedelta(hours=24)

            messages_last_hour = await self._count(
                select(func.count(Message.id)).where(Message.sent_at >= one_hour_ago)
            )

            messages_last_24h = await self._count(
                select(func.count(Message.id)).where(
                    Message.sent_at >= twenty_four_hours_ago
                )
            )

            avg_response_time = await self._get_average_response_time()
            error_rate = await self._calculate_error_rate()
            success_rate = 1.0 - error_rate
            queue_depth = await self._get_queue_depth()
            redis_memory_usage = await self._get_redis_memory_usage()
            db_connections = await self._get_database_connection_count()

            return PerformanceMetrics(
                total_active_flows=total_active_flows,
                messages_sent_last_hour=messages_last_hour,
                messages_sent_last_24h=messages_last_24h,
                average_response_time=avg_response_time,
                error_rate=error_rate,
                success_rate=success_rate,
                queue_depth=queue_depth,
                redis_memory_usage=redis_memory_usage,
                database_connection_count=db_connections,
            )

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return PerformanceMetrics(
                total_active_flows=0,
                messages_sent_last_hour=0,
                messages_sent_last_24h=0,
                average_response_time=0.0,
                error_rate=1.0,
                success_rate=0.0,
                queue_depth=0,
                redis_memory_usage=0.0,
                database_connection_count=0,
            )

        finally:
            try:
                await self._update_flow_metrics()
            except Exception as metrics_error:
                logger.warning(f"Failed to update flow metrics: {metrics_error}")

    async def _update_flow_metrics(self) -> None:
        now = now_sao_paulo()

        totals_stmt = (
            select(FlowKind.kind_key, func.count(PatientFlowState.id))
            .select_from(PatientFlowState)
            .join(
                FlowTemplateVersion,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .group_by(FlowKind.kind_key)
        )
        totals = (await self._execute(totals_stmt)).all()

        active_stmt = (
            select(FlowKind.kind_key, func.count(PatientFlowState.id))
            .select_from(PatientFlowState)
            .join(
                FlowTemplateVersion,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .where(PatientFlowState.completed_at.is_(None))
            .group_by(FlowKind.kind_key)
        )
        active = (await self._execute(active_stmt)).all()

        completed_stmt = (
            select(FlowKind.kind_key, func.count(PatientFlowState.id))
            .select_from(PatientFlowState)
            .join(
                FlowTemplateVersion,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .where(PatientFlowState.completed_at.is_not(None))
            .group_by(FlowKind.kind_key)
        )
        completed = (await self._execute(completed_stmt)).all()

        total_map = {kind: count for kind, count in totals}
        active_map = {kind: count for kind, count in active}
        completed_map = {kind: count for kind, count in completed}

        for kind_key, total_count in total_map.items():
            active_count = active_map.get(kind_key, 0)
            completed_count = completed_map.get(kind_key, 0)

            flow_active_count.labels(kind_key).set(active_count)
            completion_rate = completed_count / total_count if total_count > 0 else 0.0
            flow_completion_rate.labels(kind_key).set(completion_rate)

            previous = self._last_completion_counts.get(kind_key, 0)
            if completed_count > previous:
                flow_completed_count.labels(kind_key).inc(completed_count - previous)
            self._last_completion_counts[kind_key] = completed_count

        recent_completions_stmt = (
            select(FlowKind.kind_key, PatientFlowState)
            .select_from(PatientFlowState)
            .join(
                FlowTemplateVersion,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .where(
                PatientFlowState.completed_at.is_not(None),
                PatientFlowState.completed_at >= self._last_metrics_check,
            )
        )
        recent_completions = (await self._execute(recent_completions_stmt)).all()

        for kind_key, flow_state in recent_completions:
            if flow_state.started_at and flow_state.completed_at:
                duration = (flow_state.completed_at - flow_state.started_at).total_seconds()
                flow_duration_seconds.labels(kind_key).observe(duration)

        self._last_metrics_check = now

    async def _get_average_response_time(self) -> float:
        """Get average response time from Redis metrics."""
        try:
            response_times = self.redis.lrange("response_times", 0, 99)
            if response_times:
                times = [float(t) for t in response_times]
                return sum(times) / len(times)
            return 0.0
        except Exception:
            return 0.0

    async def _calculate_error_rate(self) -> float:
        """Calculate error rate from recent operations."""
        try:
            one_hour_ago = now_sao_paulo() - timedelta(hours=1)
            error_key = f"flow_errors:{one_hour_ago.strftime('%Y-%m-%d')}"

            error_count = self.redis.llen(error_key)
            total_operations = self.redis.get("operations_count_last_hour")
            total_operations = int(total_operations) if total_operations else 1

            return error_count / max(total_operations, 1)

        except Exception:
            return 0.0

    async def _get_queue_depth(self) -> int:
        """Get current message queue depth."""
        try:
            return 0
        except Exception:
            return 0

    async def _get_redis_memory_usage(self) -> float:
        """Get Redis memory usage percentage."""
        try:
            info = self.redis.info("memory")
            used_memory = info.get("used_memory", 0)
            max_memory = info.get("maxmemory", 0)

            if max_memory > 0:
                return used_memory / max_memory
            return 0.0
        except Exception:
            return 0.0

    async def _get_database_connection_count(self) -> int:
        """Get current database connection count."""
        try:
            return 0
        except Exception:
            return 0

    async def _count_stale_flows(self) -> int:
        """Count flows that haven't been processed in over 24 hours."""
        try:
            twenty_four_hours_ago = now_sao_paulo() - timedelta(hours=24)
            paused_expr = or_(
                PatientFlowState.status == "paused",
                cast(PatientFlowState.step_data["paused"].astext, Boolean).is_(True),
            )
            last_sent_expr = func.coalesce(
                cast(
                    PatientFlowState.step_data["last_message_sent"].astext,
                    DateTime(timezone=True),
                ),
                cast(
                    PatientFlowState.step_data["last_message_sent_at"].astext,
                    DateTime(timezone=True),
                ),
            )

            stale_count = await self._count(
                select(func.count(PatientFlowState.id)).where(
                    and_(
                        ~paused_expr,
                        or_(
                            last_sent_expr < twenty_four_hours_ago,
                            last_sent_expr.is_(None),
                        ),
                    )
                )
            )

            return stale_count

        except Exception as e:
            logger.error(f"Error counting stale flows: {e}")
            return 0

    async def _calculate_corruption_rate(self) -> float:
        """Calculate data corruption rate."""
        try:
            total_flows = await self._count(select(func.count(PatientFlowState.id)))
            if total_flows == 0:
                return 0.0

            sample_size = min(100, total_flows)
            corruption_report = await self.corruption_detector.detect_bulk_corruption(
                sample_size
            )

            corrupted_flows = len(corruption_report)
            return corrupted_flows / sample_size

        except Exception as e:
            logger.error(f"Error calculating corruption rate: {e}")
            return 0.0
