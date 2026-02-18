"""
Flow alerts service.

Generates alerts for flow health and analytics thresholds and routes them
through the unified AlertManager notification pipeline.

Architecture note (QW-021 consolidation):
    Unique alerting concern -- evaluates completion rates, duration anomalies,
    inconsistent states, and inactive templates, then routes through AlertManager.
    NOT duplicated in ``app.services.flow`` package.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List

from sqlalchemy import func, case

from app.models.flow import PatientFlowState, FlowTemplateVersion, FlowKind
from app.services.alerts import get_alert_manager
from app.services.alerts.types import Alert, AlertRuleType, AlertSeverity, AlertStatus
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowAlertsService:
    def __init__(self, db: Any):
        self.db = db
        self.alert_manager = get_alert_manager()

    async def evaluate_alerts(self) -> List[Alert]:
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        alerts: List[Alert] = []

        alerts.extend(await self._completion_rate_alerts())
        alerts.extend(await self._duration_alerts())
        alerts.extend(await self._inconsistent_state_alerts())
        alerts.extend(await self._inactive_template_alerts())

        for alert in alerts:
            try:
                await self.alert_manager.process_alert(alert)
            except Exception as exc:
                logger.warning(f"Failed to process flow alert {alert.id}: {exc}")

        return alerts

    async def _completion_rate_alerts(self) -> List[Alert]:
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        threshold = 0.5
        results = (
            self.db.query(
                FlowTemplateVersion.id,
                FlowKind.kind_key,
                func.count(PatientFlowState.id).label("total"),
                func.sum(
                    case(
                        (PatientFlowState.completed_at.is_not(None), 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .outerjoin(
                PatientFlowState,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .group_by(FlowTemplateVersion.id, FlowKind.kind_key)
            .all()
        )

        alerts: List[Alert] = []
        for template_id, kind_key, total, completed in results:
            total = total or 0
            completed = completed or 0
            if total == 0:
                continue
            completion_rate = completed / total
            if completion_rate < threshold:
                alerts.append(
                    self._build_alert(
                        severity=AlertSeverity.WARNING,
                        title="Low completion rate",
                        message=f"Completion rate {completion_rate:.2%} below {threshold:.0%}.",
                        context={
                            "template_version_id": str(template_id),
                            "flow_kind": kind_key,
                            "completion_rate": completion_rate,
                        },
                    )
                )
        return alerts

    async def _duration_alerts(self) -> List[Alert]:
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        threshold_days = 30
        duration_seconds = threshold_days * 86400

        results = (
            self.db.query(
                FlowTemplateVersion.id,
                FlowKind.kind_key,
                func.avg(
                    func.extract(
                        "epoch",
                        PatientFlowState.completed_at - PatientFlowState.started_at,
                    )
                ).label("avg_duration"),
            )
            .join(FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id)
            .join(
                PatientFlowState,
                PatientFlowState.flow_template_version_id == FlowTemplateVersion.id,
            )
            .filter(PatientFlowState.completed_at.is_not(None))
            .group_by(FlowTemplateVersion.id, FlowKind.kind_key)
            .all()
        )

        alerts: List[Alert] = []
        for template_id, kind_key, avg_duration in results:
            if avg_duration and avg_duration > duration_seconds:
                alerts.append(
                    self._build_alert(
                        severity=AlertSeverity.WARNING,
                        title="Long average flow duration",
                        message=f"Average duration {avg_duration / 86400:.1f} days exceeds {threshold_days} days.",
                        context={
                            "template_version_id": str(template_id),
                            "flow_kind": kind_key,
                            "average_duration_days": avg_duration / 86400,
                        },
                    )
                )
        return alerts

    async def _inconsistent_state_alerts(self) -> List[Alert]:
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        inconsistent = (
            self.db.query(PatientFlowState)
            .filter(
                func.coalesce(PatientFlowState.status, "") == "completed",
                PatientFlowState.completed_at.is_(None),
            )
            .all()
        )

        alerts: List[Alert] = []
        for flow_state in inconsistent:
            alerts.append(
                self._build_alert(
                    severity=AlertSeverity.CRITICAL,
                    title="Inconsistent flow state",
                    message="Flow marked completed without completed_at timestamp.",
                    context={
                        "flow_id": str(flow_state.id),
                        "patient_id": str(flow_state.patient_id),
                    },
                )
            )
        return alerts

    async def _inactive_template_alerts(self) -> List[Alert]:
        # TODO(async-migration): sync SQLAlchemy calls block event loop
        # Migration: convert self.db to AsyncSession, use await self.db.execute(select(...))
        active_templates = (
            self.db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.is_active.is_(True))
            .all()
        )

        alerts: List[Alert] = []
        for template in active_templates:
            active_patients = (
                self.db.query(PatientFlowState)
                .filter(
                    PatientFlowState.flow_template_version_id == template.id,
                    PatientFlowState.completed_at.is_(None),
                )
                .count()
            )
            if active_patients == 0:
                alerts.append(
                    self._build_alert(
                        severity=AlertSeverity.INFO,
                        title="Template without active patients",
                        message="Active template has no active patients.",
                        context={
                            "template_version_id": str(template.id),
                            "flow_kind_id": str(template.flow_kind_id),
                        },
                    )
                )
        return alerts

    def _build_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        context: Dict[str, Any],
    ) -> Alert:
        now = now_sao_paulo()
        return Alert(
            id=uuid4(),
            rule_id=uuid4(),
            rule_type=AlertRuleType.CUSTOM,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=title,
            message=message,
            context=context,
            metadata={},
            created_at=now,
        )
