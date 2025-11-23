"""
Flow Service
Business logic for patient flows and interactions.
"""

import logging
import base64
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import  joinedload
from sqlalchemy import and_

from app.models.flow import PatientFlowState as FlowStateModel, FlowTemplateVersion as FlowTemplate, FlowKind, FlowTemplateVersion # FlowRule, ABTest might be missing
from app.models.user import User
from app.models.patient import Patient
from app.schemas.v2.flows import (
    FlowStateV2Response, FlowAdvanceV2Response, FlowPauseV2Response, FlowResumeV2Response,
    FlowHistoryV2Response, FlowTemplateV2List, FlowTemplateV2Response, FlowTemplateV2Create,
    FlowTemplateV2Update, FlowCustomizationV2Response, FlowCustomizationV2Request,
    FlowRuleV2Response, FlowRuleV2Create, FlowRuleV2Update, FlowRuleV2List,
    ABTestV2Response, ABTestV2Create, ABTestV2Update, ABTestV2List, ABTestStatusV2
)
from app.services.flow_management import FlowManagementService
from app.services.analytics import FlowAnalyticsService
from app.services.flow_dashboard import FlowDashboardService
from app.domain.flows.core import FlowService
from app.exceptions import FlowStateNotFoundError, FlowStateConflictError, FlowOperationError
from app.core.redis_unified import get_async_redis

logger = logging.getLogger(__name__)

# Redis cache TTL constants (in seconds)
CACHE_TTL_DASHBOARD = 900
CACHE_TTL_ANALYTICS = 900
CACHE_TTL_RISK = 600

class FlowService:
    """Service for flow operations."""


    def _create_cursor(self, item_id: str, created_at: datetime) -> str:
        cursor_data = {"id": str(item_id), "created_at": created_at.isoformat()}
        return base64.b64encode(json.dumps(cursor_data).encode()).decode()

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

    async def get_flow_state(self, patient_id: UUID, include: Optional[List[str]]) -> FlowStateV2Response:
        flow_state = await self.flow_management.get_patient_flow_state(patient_id)
        if include:
            query = self.db.query(flow_state.__class__)
            if "patient" in include: query = query.options(joinedload(flow_state.__class__.patient))
            if "template" in include: query = query.options(joinedload(flow_state.__class__.template))
            flow_state = query.filter_by(id=flow_state.id).first()
        return flow_state

    async def advance_patient_flow(self, patient_id: UUID, force_day: Optional[int]) -> FlowAdvanceV2Response:
        advancement = await self.flow_management.advance_patient_flow(patient_id=patient_id, force_day=force_day)
        return FlowAdvanceV2Response(
            success=True, patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Flow advanced successfully")
        )

    async def pause_patient_flow(self, patient_id: UUID, reason: str, duration_hours: Optional[float], user_id: UUID) -> FlowPauseV2Response:
        pause_result = await self.flow_management.pause_patient_flow(patient_id=patient_id, reason=reason, duration_hours=duration_hours, user_id=user_id)
        return FlowPauseV2Response(
            success=True, patient_id=str(patient_id),
            paused_at=pause_result.get("paused_at", datetime.utcnow()),
            reason=reason, auto_resume_at=pause_result.get("auto_resume_at"),
            message=pause_result.get("message", "Flow paused successfully")
        )

    async def resume_patient_flow(self, patient_id: UUID, user_id: UUID) -> FlowResumeV2Response:
        resume_result = await self.flow_management.resume_patient_flow(patient_id=patient_id, user_id=user_id)
        return FlowResumeV2Response(
            success=True, patient_id=str(patient_id),
            resumed_at=resume_result.get("resumed_at", datetime.utcnow()),
            paused_duration_hours=resume_result.get("paused_duration_hours", 0.0),
            next_message_at=resume_result.get("next_message_at"),
            message=resume_result.get("message", "Flow resumed successfully")
        )

    async def get_patient_flow_history(self, patient_id: UUID, pagination: Dict, include: Optional[List[str]]) -> FlowHistoryV2Response:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]
        query = self.db.query(FlowStateModel).filter(FlowStateModel.patient_id == patient_id)

        if include:
            if "patient" in include: query = query.options(joinedload(FlowStateModel.patient))
            if "template" in include: query = query.options(joinedload(FlowStateModel.template))

        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
            query = query.filter((FlowStateModel.created_at < cursor_created) | ((FlowStateModel.created_at == cursor_created) & (FlowStateModel.id > cursor_id)))

        total = query.count() if not cursor_data else None
        query = query.order_by(FlowStateModel.created_at.desc(), FlowStateModel.id)
        flow_states = query.limit(limit + 1).all()

        has_more = len(flow_states) > limit
        if has_more: flow_states = flow_states[:limit]
        
        next_cursor = self._create_cursor(flow_states[-1].id, flow_states[-1].created_at) if has_more and flow_states else None
        current_flow = await self.flow_management.get_patient_flow_state(patient_id)

        return FlowHistoryV2Response(
            patient_id=str(patient_id),
            data=[FlowStateV2Response.from_orm(fs) for fs in flow_states],
            next_cursor=next_cursor, has_more=has_more, total=total,
            current_flow=FlowStateV2Response.from_orm(current_flow) if current_flow else None
        )

    async def get_dashboard_overview(self, timeframe: str, user_id: UUID) -> Dict[str, Any]:
        cache_key = f"flow:dashboard:overview:{timeframe}:{user_id}"
        async def compute():
            return await self.flow_dashboard.get_dashboard_overview(timeframe)
        return await self._get_cached_or_compute(cache_key, compute, CACHE_TTL_DASHBOARD)

    async def list_templates(self, pagination: Dict, flow_type: Optional[str], active_only: bool) -> FlowTemplateV2List:
        cursor_data = pagination["cursor_data"]
        limit = pagination["limit"]
        query = self.db.query(FlowTemplate)
        
        filters = []
        if active_only: filters.append(FlowTemplate.is_active == True)
        if flow_type: filters.append(FlowTemplate.flow_type == flow_type)
        
        if cursor_data and "id" in cursor_data:
            cursor_id = UUID(cursor_data["id"])
            cursor_created = datetime.fromisoformat(cursor_data["created_at"].replace("Z", "+00:00"))
            filters.append((FlowTemplate.created_at < cursor_created) | ((FlowTemplate.created_at == cursor_created) & (FlowTemplate.id > cursor_id)))
            
        if filters: query = query.filter(and_(*filters))
        
        total = query.count() if not cursor_data else None
        query = query.order_by(FlowTemplate.created_at.desc(), FlowTemplate.id)
        templates = query.limit(limit + 1).all()
        
        has_more = len(templates) > limit
        if has_more: templates = templates[:limit]
        
        next_cursor = self._create_cursor(templates[-1].id, templates[-1].created_at) if has_more and templates else None
        
        return FlowTemplateV2List(
            data=[FlowTemplateV2Response.from_orm(t) for t in templates],
            next_cursor=next_cursor, has_more=has_more, total=total
        )

    async def start_patient_flow(self, patient_id: UUID, flow_type: str, user_id: UUID) -> FlowStateV2Response:
        flow_state = await self.flow_management.start_patient_flow(patient_id=patient_id, flow_type=flow_type)
        return FlowStateV2Response.from_orm(flow_state)

    async def process_patient_response(self, patient_id: UUID, response_text: str, metadata: Dict[str, Any]) -> FlowAdvanceV2Response:
        advancement = await self.flow_management.process_patient_response(patient_id=patient_id, response_text=response_text, response_metadata=metadata)
        return FlowAdvanceV2Response(
            success=True, patient_id=str(patient_id),
            previous_step=advancement.get("previous_step", 0),
            current_step=advancement.get("current_step", 0),
            next_actions=advancement.get("next_actions", []),
            message=advancement.get("message", "Response processed successfully")
        )
