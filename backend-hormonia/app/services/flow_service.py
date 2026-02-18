"""
Flow Service - V2 API facade for patient flow operations.

Acts as the top-level orchestrator consumed by the V2 REST layer.
Delegates to FlowManagement, FlowAnalytics, FlowDashboard, and EnhancedFlowEngine.
Extends FlowCore for shared treatment-flow operations.

Architecture note (QW-021 consolidation):
    This facade provides cursor-based pagination, Redis caching, and V2 schema
    mapping that do NOT exist in the ``app.services.flow`` package.
    NOT a duplicate -- it is the API-facing service layer.

    Canonical FlowType enum: ``app.services.flow.types.FlowType``
"""

import logging
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.orm import joinedload
from sqlalchemy import and_

from app.models.flow import PatientFlowState as FlowStateModel, FlowTemplateVersion, FlowKind
from app.schemas.v2.flows import (
    FlowStateV2Response,
    FlowAdvanceV2Response,
    FlowPauseV2Response,
    FlowResumeV2Response,
    FlowHistoryV2Response,
    FlowTemplateV2List,
    FlowTemplateV2Response,
)
from app.services.flow_core import FlowCore
from app.services.flow_management import FlowManagementService
from app.services.analytics.flow_analytics import FlowAnalyticsService
from app.services.flow_dashboard import FlowDashboardService
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.core.redis_manager import get_async_redis_client as get_async_redis
from app.exceptions import (
    FlowStateNotFoundError,
    FlowStateConflictError,
    FlowOperationError,
    FlowValidationError,
    NotFoundError as DomainNotFoundError,
)
from app.core.exceptions import NotFoundError, BusinessRuleError
from app.utils.cursor import encode_cursor
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

# Redis cache TTL constants (in seconds)
CACHE_TTL_DASHBOARD = 900
CACHE_TTL_ANALYTICS = 900
CACHE_TTL_RISK = 600


class FlowService(FlowCore):
    """
    Service for flow operations.
    Acts as a facade for FlowManagement, Analytics, Dashboard, and Engine.
    """

    def __init__(
        self,
        db: Any,
        flow_management: FlowManagementService,
        flow_analytics: FlowAnalyticsService,
        flow_dashboard: FlowDashboardService,
        flow_engine: EnhancedFlowEngine,
    ):
        super().__init__(db)
        self.flow_management = flow_management
        self.flow_analytics = flow_analytics
        self.flow_dashboard = flow_dashboard
        self.enhanced_flow_engine = flow_engine
        # Ensure compatibility with FlowCore if it uses platform_sync/template_loader internally
        # (FlowCore init handles this if we pass args, but here we just pass db and let it default)

    def _create_cursor(self, item_id: str, created_at: datetime) -> str:
        return encode_cursor(item_id, created_at)

    async def _get_cached_or_compute(self, cache_key: str, compute_fn, ttl: int) -> Any:
        redis_cache = await get_async_redis()
        if redis_cache:
            cached = await redis_cache.get(cache_key)
            if cached:
                return json.loads(cached)

        result = await compute_fn()

        if redis_cache:
            await redis_cache.setex(cache_key, ttl, json.dumps(result, default=str))

        return result

    async def get_flow_state(
        self, patient_id: UUID, include: Optional[List[str]]
    ) -> FlowStateV2Response:
        from app.schemas.v2.flows import FlowStatusV2
        
        # Get the flow state from flow_management (returns FlowStateResponse)
        flow_state_response = await self.flow_management.get_patient_flow_state(patient_id)
        
        # If no active flow, return a minimal response
        if not flow_state_response.has_active_flow:
            # Return a response indicating no active flow
            return FlowStateV2Response(
                id="",
                patient_id=str(patient_id),
                flow_type="none",
                template_version="",
                current_step=0,
                status=FlowStatusV2.COMPLETED,
                started_at=now_sao_paulo(),
                state_data={"message": flow_state_response.message or "No active flow"},
            )
        
        # Extract data from the nested flow_state dict
        flow_data = flow_state_response.flow_state or {}
        
        # Map is_paused to status
        is_paused = flow_data.get("is_paused", False)
        if is_paused:
            status = FlowStatusV2.PAUSED
        elif flow_data.get("completed_at"):
            status = FlowStatusV2.COMPLETED
        else:
            status = FlowStatusV2.ACTIVE
        
        # Parse started_at
        started_at_str = flow_data.get("started_at")
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str)
            except (ValueError, AttributeError):
                started_at = now_sao_paulo()
        else:
            started_at = now_sao_paulo()
        
        # Parse completed_at if present
        completed_at = None
        completed_at_str = flow_data.get("completed_at")
        if completed_at_str:
            try:
                completed_at = datetime.fromisoformat(completed_at_str)
            except (ValueError, AttributeError):
                pass
        
        return FlowStateV2Response(
            id=flow_data.get("id", ""),
            patient_id=str(patient_id),
            flow_type=flow_data.get("flow_type", "unknown"),
            template_version=flow_data.get("template_version", "1.0.0"),
            current_step=flow_data.get("current_step", 0),
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            state_data=flow_data.get("state_data", {}),
        )

    async def advance_patient_flow(
        self, patient_id: UUID, force_day: Optional[int]
    ) -> FlowAdvanceV2Response:
        try:
            advancement = await self.flow_management.advance_patient_flow(
                patient_id=patient_id, force_day=force_day
            )
        except (FlowStateNotFoundError, DomainNotFoundError) as e:
            raise NotFoundError("Flow state", patient_id) from e
        except (FlowStateConflictError, FlowValidationError, FlowOperationError) as e:
            raise BusinessRuleError(str(e)) from e
        logger.info(
            "Flow advanced via API",
            extra={
                "patient_id": str(patient_id),
                "previous_step": advancement.get("previous_step"),
                "current_step": advancement.get("current_step"),
            },
        )
        return FlowAdvanceV2Response(
            success=True,
            patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Flow advanced successfully"),
        )

    async def pause_patient_flow(
        self,
        patient_id: UUID,
        reason: str,
        duration_hours: Optional[float],
        user_id: UUID,
    ) -> FlowPauseV2Response:
        try:
            pause_result = await self.flow_management.pause_patient_flow(
                patient_id=patient_id,
                reason=reason,
                duration_hours=duration_hours,
                user_id=user_id,
            )
        except (FlowStateNotFoundError, DomainNotFoundError) as e:
            raise NotFoundError("Flow state", patient_id) from e
        except (FlowStateConflictError, FlowValidationError, FlowOperationError) as e:
            raise BusinessRuleError(str(e)) from e
        logger.info(
            "Flow paused via API",
            extra={
                "patient_id": str(patient_id),
                "reason": reason,
                "auto_resume_at": pause_result.get("auto_resume_at"),
            },
        )
        return FlowPauseV2Response(
            success=True,
            patient_id=str(patient_id),
            paused_at=pause_result.get("paused_at", now_sao_paulo()),
            reason=reason,
            auto_resume_at=pause_result.get("auto_resume_at"),
            message=pause_result.get("message", "Flow paused successfully"),
        )

    async def resume_patient_flow(
        self, patient_id: UUID, user_id: UUID
    ) -> FlowResumeV2Response:
        try:
            resume_result = await self.flow_management.resume_patient_flow(
                patient_id=patient_id, user_id=user_id
            )
        except (FlowStateNotFoundError, DomainNotFoundError) as e:
            raise NotFoundError("Flow state", patient_id) from e
        except (FlowStateConflictError, FlowValidationError, FlowOperationError) as e:
            raise BusinessRuleError(str(e)) from e
        logger.info(
            "Flow resumed via API",
            extra={
                "patient_id": str(patient_id),
                "resumed_at": resume_result.get("resumed_at"),
            },
        )
        return FlowResumeV2Response(
            success=True,
            patient_id=str(patient_id),
            resumed_at=resume_result.get("resumed_at", now_sao_paulo()),
            paused_duration_hours=resume_result.get("paused_duration_hours", 0.0),
            next_message_at=resume_result.get("next_message_at"),
            message=resume_result.get("message", "Flow resumed successfully"),
        )

    async def get_patient_flow_history(
        self, patient_id: UUID, pagination: Dict, include: Optional[List[str]]
    ) -> FlowHistoryV2Response:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]
        query = self.db.query(FlowStateModel).filter(
            FlowStateModel.patient_id == patient_id
        )

        if include:
            if "patient" in include:
                query = query.options(joinedload(FlowStateModel.patient))
            if "template" in include:
                query = query.options(joinedload(FlowStateModel.template_version))

        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(
                cursor_data["created_at"]
            )
            query = query.filter(
                (FlowStateModel.created_at < cursor_created)
                | (
                    (FlowStateModel.created_at == cursor_created)
                    & (FlowStateModel.id > cursor_id)
                )
            )

        total = query.count() if not cursor_data else None
        query = query.order_by(FlowStateModel.created_at.desc(), FlowStateModel.id)
        flow_states = query.limit(limit + 1).all()

        has_more = len(flow_states) > limit
        if has_more:
            flow_states = flow_states[:limit]

        next_cursor = (
            self._create_cursor(flow_states[-1].id, flow_states[-1].created_at)
            if has_more and flow_states
            else None
        )
        current_flow = await self.flow_management.get_patient_flow_state(patient_id)
        current_flow_v2 = None
        if current_flow and getattr(current_flow, "has_active_flow", False):
            flow_data = current_flow.flow_state or {}
            is_paused = flow_data.get("is_paused", False)
            if is_paused:
                status = FlowStatusV2.PAUSED
            elif flow_data.get("completed_at"):
                status = FlowStatusV2.COMPLETED
            else:
                status = FlowStatusV2.ACTIVE

            started_at = now_sao_paulo()
            started_at_str = flow_data.get("started_at")
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str)
                except (ValueError, AttributeError):
                    pass

            completed_at = None
            completed_at_str = flow_data.get("completed_at")
            if completed_at_str:
                try:
                    completed_at = datetime.fromisoformat(completed_at_str)
                except (ValueError, AttributeError):
                    completed_at = None

            current_flow_v2 = FlowStateV2Response(
                id=flow_data.get("id", ""),
                patient_id=str(patient_id),
                flow_type=flow_data.get("flow_type", "unknown"),
                template_version=flow_data.get("template_version", "1.0.0"),
                current_step=flow_data.get("current_step", 0),
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                state_data=flow_data.get("state_data", {}),
            )

        return FlowHistoryV2Response(
            patient_id=str(patient_id),
            data=[FlowStateV2Response.from_orm(fs) for fs in flow_states],
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            current_flow=current_flow_v2,
        )

    async def get_dashboard_overview(
        self, timeframe: str, user_id: UUID
    ) -> Dict[str, Any]:
        cache_key = f"flow:dashboard:overview:{timeframe}:{user_id}"

        async def compute():
            return await self.flow_dashboard.get_dashboard_overview(timeframe)

        return await self._get_cached_or_compute(
            cache_key, compute, CACHE_TTL_DASHBOARD
        )

    async def list_templates(
        self, pagination: Dict, flow_type: Optional[str], active_only: bool
    ) -> FlowTemplateV2List:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]

        # Use FlowTemplateVersion with join to FlowKind for flow_type filtering
        query = self.db.query(FlowTemplateVersion).join(
            FlowKind, FlowTemplateVersion.flow_kind_id == FlowKind.id
        )

        filters = []
        if active_only:
            filters.append(FlowTemplateVersion.is_active == True)
        if flow_type:
            filters.append(FlowKind.kind_key == flow_type)

        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(
                cursor_data["created_at"]
            )
            filters.append(
                (FlowTemplateVersion.created_at < cursor_created)
                | (
                    (FlowTemplateVersion.created_at == cursor_created)
                    & (FlowTemplateVersion.id > cursor_id)
                )
            )

        if filters:
            query = query.filter(and_(*filters))

        total = query.count() if not cursor_data else None
        query = query.order_by(FlowTemplateVersion.created_at.desc(), FlowTemplateVersion.id)
        templates = query.limit(limit + 1).all()

        has_more = len(templates) > limit
        if has_more:
            templates = templates[:limit]

        next_cursor = (
            self._create_cursor(templates[-1].id, templates[-1].created_at)
            if has_more and templates
            else None
        )

        return FlowTemplateV2List(
            data=[FlowTemplateV2Response.from_orm(t) for t in templates],
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
        )

    async def start_patient_flow(
        self, patient_id: UUID, flow_type: str, user_id: UUID
    ) -> FlowStateV2Response:
        try:
            flow_state = await self.flow_management.start_patient_flow(
                patient_id=patient_id, flow_type=flow_type
            )
        except (FlowStateNotFoundError, DomainNotFoundError) as e:
            raise NotFoundError("Flow state", patient_id) from e
        except (FlowStateConflictError, FlowValidationError, FlowOperationError) as e:
            raise BusinessRuleError(str(e)) from e
        return FlowStateV2Response.from_orm(flow_state)

    async def process_patient_response(
        self, patient_id: UUID, response_text: str, metadata: Dict[str, Any]
    ) -> FlowAdvanceV2Response:
        try:
            advancement = await self.flow_management.process_patient_response(
                patient_id=patient_id,
                response_text=response_text,
                response_metadata=metadata,
            )
        except (FlowStateNotFoundError, DomainNotFoundError) as e:
            raise NotFoundError("Flow state", patient_id) from e
        except (FlowStateConflictError, FlowValidationError, FlowOperationError) as e:
            raise BusinessRuleError(str(e)) from e
        return FlowAdvanceV2Response(
            success=True,
            patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Response processed successfully"),
        )
