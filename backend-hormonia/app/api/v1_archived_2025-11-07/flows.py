"""
Flow management and analytics endpoints for Hormonia Backend System.
"""
import logging
from fastapi import APIRouter, Depends, Query, Request
from typing import List, Optional, Any
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rls_middleware import (
    get_jwt_token, get_user_context, require_authentication,
    optional_authentication, rls_middleware
)
from app.core.database import RLSError, RLSAccessDeniedError
from app.services.flow_dashboard import FlowDashboardService, DashboardTimeframe, get_flow_dashboard_service
from app.services.flow_analytics import RiskLevel, FlowAnalyticsService
from app.dependencies.service_dependencies import get_flow_analytics_service
from app.services.flow import FlowEngineIntegrationService
from app.services.patient import PatientService
from app.schemas.flow import FlowAnalytics as FlowAnalyticsSchema
from app.dependencies import (
    get_current_user,
    validate_patient_access,
    get_flow_management_service,
    get_patient_service,
    get_flow_service
)


from app.exceptions import (
    FlowStateNotFoundError,
    FlowOperationError,
    FlowStateConflictError,
    PatientNotFoundError,
    PatientAccessDeniedError,
    flow_not_found_exception,
    flow_operation_exception,
    internal_server_exception
)
from app.models.user import User
from app.models.patient import Patient
from app.services.flow_management import FlowManagementService
from app.schemas.flow import (
    FlowStateResponse,
    FlowAdvancementResponse,
    FlowPauseResponse,
    FlowResumeResponse,
    FlowHistoryResponse,
    FlowPauseRequest,
    FlowAdvanceRequest,
    FlowTemplateResponse,
    FlowTemplateCreate,
    FlowTemplateUpdate,
    FlowCustomizationRequest,
    FlowCustomizationResponse,
    FlowRuleRequest,
    FlowRuleResponse,
    ABTestConfigRequest,
    ABTestConfigResponse,
    StartFlowRequest,
    ProcessResponseRequest
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Flow service dependency moved to dependencies.py


# Flow State Management Endpoints
@router.get("/{patient_id}/state", response_model=FlowStateResponse)
async def get_flow_state(
    patient_id: UUID,
    patient: Patient = Depends(validate_patient_access),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowStateResponse:
    """
    Get patient's current flow state.
    
    Returns detailed information about the patient's current conversation flow,
    including current day, flow type, and state data.
    """
    try:
        return await flow_management.get_patient_flow_state(patient_id)
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowOperationError as e:
        raise flow_operation_exception("get_state", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting flow state for patient {patient_id}")
        raise internal_server_exception("Failed to get flow state")


@router.post("/{patient_id}/advance", response_model=FlowAdvancementResponse)
async def advance_patient_flow(
    patient_id: UUID,
    request: FlowAdvanceRequest,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowAdvancementResponse:
    """
    Manually advance patient flow.
    
    Advances the patient to the next appropriate flow step or to a specific day
    if force_day is provided. This is useful for healthcare providers who need
    to manually control flow progression.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        return await flow_management.advance_patient_flow(
            patient_id=patient_id,
            force_day=request.force_day
        )
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowOperationError as e:
        raise flow_operation_exception("advance_flow", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error advancing flow for patient {patient_id}")
        raise internal_server_exception("Failed to advance flow")


@router.post("/{patient_id}/pause", response_model=FlowPauseResponse)
async def pause_patient_flow(
    patient_id: UUID,
    request: Optional[FlowPauseRequest] = None,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowPauseResponse:
    """
    Pause patient flow.
    
    Temporarily pauses the conversation flow for a patient. Messages will not
    be sent while the flow is paused. Optionally specify a duration after which
    the flow will automatically resume.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        # Use defaults if no request body provided
        reason = request.reason if request else "Manual pause"
        duration_hours = request.duration_hours if request else None

        return await flow_management.pause_patient_flow(
            patient_id=patient_id,
            reason=reason,
            duration_hours=duration_hours,
            user_id=current_user.id
        )
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowStateConflictError as e:
        raise flow_operation_exception("pause_flow", str(e))
    except FlowOperationError as e:
        raise flow_operation_exception("pause_flow", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error pausing flow for patient {patient_id}")
        raise internal_server_exception("Failed to pause flow")


@router.post("/{patient_id}/resume", response_model=FlowResumeResponse)
async def resume_patient_flow(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowResumeResponse:
    """
    Resume patient flow.
    
    Resumes a previously paused conversation flow. The patient will continue
    from where they left off without missing any messages.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        return await flow_management.resume_patient_flow(
            patient_id=patient_id,
            user_id=current_user.id
        )
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except FlowStateConflictError as e:
        raise flow_operation_exception("resume_flow", str(e))
    except FlowOperationError as e:
        raise flow_operation_exception("resume_flow", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error resuming flow for patient {patient_id}")
        raise internal_server_exception("Failed to resume flow")


@router.get("/{patient_id}/history", response_model=FlowHistoryResponse)
async def get_patient_flow_history(
    patient_id: UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowHistoryResponse:
    """
    Get patient flow history.
    
    Returns a paginated list of all flow states for the patient,
    including completed and current flows.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        return await flow_management.get_patient_flow_history(
            patient_id=patient_id,
            skip=skip,
            limit=limit
        )
        
    except FlowOperationError as e:
        raise flow_operation_exception("get_history", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error getting flow history for patient {patient_id}")
        raise internal_server_exception("Failed to get flow history")


# Analytics Dashboard Endpoints
@router.get("/dashboard/overview")
async def get_dashboard_overview(
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_7_DAYS, description="Time period for dashboard data"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Get flow dashboard overview with key metrics.
    
    Returns comprehensive dashboard data including:
    - Active flow counts by type
    - Completion rates and trends
    - Patient engagement metrics
    - Alert summaries
    """
    try:
        dashboard_service = get_flow_dashboard_service(db)
        overview_data = await dashboard_service.get_dashboard_overview(timeframe)
        return {
            "success": True,
            "timeframe": timeframe.value,
            "data": overview_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard overview: {e}")
        raise internal_server_exception("Failed to get dashboard overview")


@router.get("/dashboard/flow-metrics")
async def get_flow_metrics(
    flow_type: Optional[str] = Query(None, description="Filter by specific flow type"),
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS, description="Time period for metrics"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Get detailed flow performance metrics.
    
    Returns metrics including:
    - Flow completion rates by type
    - Average completion times
    - Step-by-step progression analysis
    - Drop-off points identification
    """
    try:
        dashboard_service = get_flow_dashboard_service(db)
        metrics_data = await dashboard_service.get_flow_metrics(
            flow_type=flow_type,
            timeframe=timeframe
        )
        return {
            "success": True,
            "flow_type": flow_type,
            "timeframe": timeframe.value,
            "metrics": metrics_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get flow metrics: {e}")
        raise internal_server_exception("Failed to get flow metrics")


@router.get("/dashboard/patient-engagement")
async def get_patient_engagement_metrics(
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS, description="Time period for engagement data"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Get patient engagement analytics.
    
    Returns engagement data including:
    - Response rates and timing
    - Message interaction patterns
    - Patient satisfaction indicators
    - Engagement trends over time
    """
    try:
        dashboard_service = get_flow_dashboard_service(db)
        engagement_data = await dashboard_service.get_patient_engagement_metrics(timeframe)
        return {
            "success": True,
            "timeframe": timeframe.value,
            "engagement_metrics": engagement_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get patient engagement metrics: {e}")
        raise internal_server_exception("Failed to get patient engagement metrics")


# Flow Analytics Endpoints
@router.get("/analytics/risk-assessment")
async def get_risk_assessment(
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of patients to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Get patient risk assessment based on flow analytics.
    
    Analyzes patient flow patterns to identify:
    - High-risk patients requiring immediate attention
    - Patients with declining engagement
    - Potential treatment adherence issues
    - Recommended interventions
    """
    try:
        analytics_service = get_flow_analytics_service(db)
        risk_data = await analytics_service.analyze_patient_risk(
            risk_level=risk_level,
            limit=limit
        )
        return {
            "success": True,
            "risk_level_filter": risk_level.value if risk_level else "all",
            "risk_assessments": risk_data,
            "total_patients": len(risk_data),
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get risk assessment: {e}")
        raise internal_server_exception("Failed to get risk assessment")


@router.get("/analytics/flow-performance", response_model=List[FlowAnalyticsSchema])
async def get_flow_performance_analytics(
    flow_type: Optional[str] = Query(None, description="Filter by specific flow type"),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis period"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis period"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[FlowAnalyticsSchema]:
    """
    Get comprehensive flow performance analytics.

    Provides detailed analysis including:
    - Flow completion rates and trends
    - Step-by-step performance metrics
    - Patient progression patterns
    - Optimization recommendations
    """
    try:
        analytics_service = get_flow_analytics_service(db)
        analytics_data = await analytics_service.get_flow_performance_analytics(
            flow_type=flow_type,
            start_date=start_date,
            end_date=end_date
        )
        return analytics_data
    except Exception as e:
        logger.error(f"Failed to get flow performance analytics: {e}")
        raise internal_server_exception("Failed to get flow performance analytics")


@router.get("/analytics/patient-journey")
async def get_patient_journey_analytics(
    patient_id: Optional[UUID] = Query(None, description="Specific patient ID for detailed journey"),
    flow_type: Optional[str] = Query(None, description="Filter by flow type"),
    timeframe: DashboardTimeframe = Query(DashboardTimeframe.LAST_30_DAYS, description="Analysis timeframe"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Get patient journey analytics and insights.
    
    Analyzes patient interactions and flow progression to provide:
    - Individual patient journey mapping
    - Common pathway analysis
    - Intervention effectiveness
    - Personalization opportunities
    """
    try:
        analytics_service = get_flow_analytics_service(db)
        journey_data = await analytics_service.analyze_patient_journeys(
            patient_id=patient_id,
            flow_type=flow_type,
            timeframe=timeframe
        )
        return {
            "success": True,
            "patient_id": str(patient_id) if patient_id else None,
            "flow_type": flow_type,
            "timeframe": timeframe.value,
            "journey_analytics": journey_data,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get patient journey analytics: {e}")
        raise internal_server_exception("Failed to get patient journey analytics")


@router.post("/analytics/generate-insights", response_model=None)
async def generate_flow_insights(
    flow_type: Optional[str] = Query(None, description="Focus on specific flow type"),
    analysis_depth: str = Query("standard", regex="^(basic|standard|detailed)$", description="Depth of analysis"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, Any]:
    """
    Generate AI-powered insights from flow analytics data.
    
    Uses advanced analytics to provide:
    - Automated pattern recognition
    - Predictive insights
    - Optimization recommendations
    - Actionable improvement suggestions
    """
    try:
        analytics_service = get_flow_analytics_service(db)
        insights = await analytics_service.generate_ai_insights(
            flow_type=flow_type,
            analysis_depth=analysis_depth
        )
        return {
            "success": True,
            "flow_type": flow_type,
            "analysis_depth": analysis_depth,
            "insights": insights,
            "generated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to generate flow insights: {e}")
        raise internal_server_exception("Failed to generate flow insights")

# Flow Configuration and Customization Endpoints
@router.get("/templates", response_model=List[FlowTemplateResponse])
async def get_flow_templates(
    skip: int = Query(0, ge=0, description="Number of templates to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of templates to return"),
    flow_type: Optional[str] = Query(None, description="Filter by flow type"),
    active_only: bool = Query(True, description="Return only active templates"),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> List[FlowTemplateResponse]:
    """
    Get flow templates for healthcare administrators.
    
    Returns paginated list of flow templates that can be used to configure
    patient conversation flows. Templates define message content, timing,
    and conditional logic.
    """
    try:
        templates = await flow_management.get_flow_templates(
            skip=skip,
            limit=limit,
            flow_type=flow_type,
            active_only=active_only
        )
        return templates
        
    except Exception as e:
        logger.error(f"Failed to get flow templates: {e}")
        raise internal_server_exception("Failed to get flow templates")


@router.post("/templates", response_model=FlowTemplateResponse)
async def create_flow_template(
    template_data: FlowTemplateCreate,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowTemplateResponse:
    """
    Create new flow template.
    
    Creates a new conversation flow template that can be used for patient
    communication. Templates include message content, AI instructions,
    and conditional logic for personalization.
    """
    try:
        template = await flow_management.create_flow_template(
            template_data=template_data,
            created_by=current_user.id
        )
        return template
        
    except ValidationError as e:
        raise flow_operation_exception("create_template", str(e))
    except Exception as e:
        logger.error(f"Failed to create flow template: {e}")
        raise internal_server_exception("Failed to create flow template")


@router.get("/templates/{template_id}", response_model=FlowTemplateResponse)
async def get_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowTemplateResponse:
    """
    Get specific flow template by ID.
    
    Returns detailed information about a flow template including
    all message templates, AI instructions, and configuration.
    """
    try:
        template = await flow_management.get_flow_template(template_id)
        return template
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to get flow template {template_id}: {e}")
        raise internal_server_exception("Failed to get flow template")


@router.put("/templates/{template_id}", response_model=FlowTemplateResponse)
async def update_flow_template(
    template_id: UUID,
    template_data: FlowTemplateUpdate,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowTemplateResponse:
    """
    Update existing flow template.
    
    Updates flow template configuration, message content, or AI instructions.
    Changes will apply to new patient flows using this template.
    """
    try:
        template = await flow_management.update_flow_template(
            template_id=template_id,
            template_data=template_data,
            updated_by=current_user.id
        )
        return template
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except ValidationError as e:
        raise flow_operation_exception("update_template", str(e))
    except Exception as e:
        logger.error(f"Failed to update flow template {template_id}: {e}")
        raise internal_server_exception("Failed to update flow template")


@router.delete("/templates/{template_id}", response_model=None)
async def delete_flow_template(
    template_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> dict[str, Any]:
    """
    Delete flow template.
    
    Soft deletes a flow template by marking it as inactive.
    Existing patient flows using this template will continue unchanged.
    """
    try:
        await flow_management.delete_flow_template(
            template_id=template_id,
            deleted_by=current_user.id
        )
        return {"success": True, "message": "Flow template deleted successfully"}
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"template_{template_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow template {template_id}: {e}")
        raise internal_server_exception("Failed to delete flow template")


@router.post("/{patient_id}/customize", response_model=FlowCustomizationResponse)
async def customize_patient_flow(
    patient_id: UUID,
    customization_data: FlowCustomizationRequest,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowCustomizationResponse:
    """
    Create patient-specific flow customization.
    
    Allows healthcare providers to customize conversation flows for individual
    patients based on their specific needs, preferences, or medical conditions.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        customization = await flow_management.customize_patient_flow(
            patient_id=patient_id,
            customization_data=customization_data,
            customized_by=current_user.id
        )
        return customization
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except ValidationError as e:
        raise flow_operation_exception("customize_flow", str(e))
    except Exception as e:
        logger.error(f"Failed to customize flow for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to customize patient flow")


@router.get("/{patient_id}/customization", response_model=FlowCustomizationResponse)
async def get_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowCustomizationResponse:
    """
    Get patient's flow customization settings.
    
    Returns current customization settings for the patient's conversation flow,
    including personalized message templates and conditional logic.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        customization = await flow_management.get_patient_flow_customization(patient_id)
        return customization
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to get flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to get flow customization")


@router.put("/{patient_id}/customization", response_model=FlowCustomizationResponse)
async def update_patient_flow_customization(
    patient_id: UUID,
    customization_data: FlowCustomizationRequest,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowCustomizationResponse:
    """
    Update patient's flow customization.
    
    Updates existing customization settings for the patient's conversation flow.
    Changes will apply to future messages in the flow.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        customization = await flow_management.update_patient_flow_customization(
            patient_id=patient_id,
            customization_data=customization_data,
            updated_by=current_user.id
        )
        return customization
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except ValidationError as e:
        raise flow_operation_exception("update_customization", str(e))
    except Exception as e:
        logger.error(f"Failed to update flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to update flow customization")


@router.delete("/{patient_id}/customization", response_model=None)
async def remove_patient_flow_customization(
    patient_id: UUID,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> dict[str, Any]:
    """
    Remove patient's flow customization.
    
    Removes all customization settings for the patient, reverting to
    default flow template behavior.
    """
    # Validate patient access
    patient = await validate_patient_access(patient_id, current_user, patient_service)
    
    try:
        await flow_management.remove_patient_flow_customization(
            patient_id=patient_id,
            removed_by=current_user.id
        )
        return {"success": True, "message": "Flow customization removed successfully"}
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to remove flow customization for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to remove flow customization")


@router.post("/rules", response_model=FlowRuleResponse)
async def create_flow_rule(
    rule_data: FlowRuleRequest,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowRuleResponse:
    """
    Create flow rule for conditional logic.
    
    Creates conditional rules that control flow behavior based on patient
    responses, medical data, or other criteria. Rules can trigger different
    message paths, escalations, or customizations.
    """
    try:
        rule = await flow_management.create_flow_rule(
            rule_data=rule_data,
            created_by=current_user.id
        )
        return rule
        
    except ValidationError as e:
        raise flow_operation_exception("create_rule", str(e))
    except Exception as e:
        logger.error(f"Failed to create flow rule: {e}")
        raise internal_server_exception("Failed to create flow rule")


@router.get("/rules", response_model=List[FlowRuleResponse])
async def get_flow_rules(
    skip: int = Query(0, ge=0, description="Number of rules to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of rules to return"),
    flow_type: Optional[str] = Query(None, description="Filter by flow type"),
    active_only: bool = Query(True, description="Return only active rules"),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> List[FlowRuleResponse]:
    """
    Get flow rules.
    
    Returns paginated list of conditional flow rules that control
    conversation flow behavior and customization.
    """
    try:
        rules = await flow_management.get_flow_rules(
            skip=skip,
            limit=limit,
            flow_type=flow_type,
            active_only=active_only
        )
        return rules
        
    except Exception as e:
        logger.error(f"Failed to get flow rules: {e}")
        raise internal_server_exception("Failed to get flow rules")


@router.put("/rules/{rule_id}", response_model=FlowRuleResponse)
async def update_flow_rule(
    rule_id: UUID,
    rule_data: FlowRuleRequest,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> FlowRuleResponse:
    """
    Update flow rule.
    
    Updates conditional logic rule configuration. Changes will apply
    to future flow executions that match the rule criteria.
    """
    try:
        rule = await flow_management.update_flow_rule(
            rule_id=rule_id,
            rule_data=rule_data,
            updated_by=current_user.id
        )
        return rule
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"rule_{rule_id}")
    except ValidationError as e:
        raise flow_operation_exception("update_rule", str(e))
    except Exception as e:
        logger.error(f"Failed to update flow rule {rule_id}: {e}")
        raise internal_server_exception("Failed to update flow rule")


@router.delete("/rules/{rule_id}", response_model=None)
async def delete_flow_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> dict[str, Any]:
    """
    Delete flow rule.
    
    Removes conditional flow rule. Existing flows using this rule
    will continue with their current behavior.
    """
    try:
        await flow_management.delete_flow_rule(
            rule_id=rule_id,
            deleted_by=current_user.id
        )
        return {"success": True, "message": "Flow rule deleted successfully"}
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"rule_{rule_id}")
    except Exception as e:
        logger.error(f"Failed to delete flow rule {rule_id}: {e}")
        raise internal_server_exception("Failed to delete flow rule")


# A/B Testing Endpoints
@router.post("/ab-tests", response_model=ABTestConfigResponse)
async def create_ab_test(
    test_config: ABTestConfigRequest,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> ABTestConfigResponse:
    """
    Create A/B test configuration.
    
    Sets up A/B testing for different message approaches, allowing
    healthcare teams to optimize conversation flows based on patient
    engagement and outcomes.
    """
    try:
        ab_test = await flow_management.create_ab_test(
            test_config=test_config,
            created_by=current_user.id
        )
        return ab_test
        
    except ValidationError as e:
        raise flow_operation_exception("create_ab_test", str(e))
    except Exception as e:
        logger.error(f"Failed to create A/B test: {e}")
        raise internal_server_exception("Failed to create A/B test")


@router.get("/ab-tests", response_model=List[ABTestConfigResponse])
async def get_ab_tests(
    skip: int = Query(0, ge=0, description="Number of tests to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of tests to return"),
    active_only: bool = Query(True, description="Return only active tests"),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> List[ABTestConfigResponse]:
    """
    Get A/B test configurations.
    
    Returns paginated list of A/B tests with their current status,
    performance metrics, and configuration details.
    """
    try:
        ab_tests = await flow_management.get_ab_tests(
            skip=skip,
            limit=limit,
            active_only=active_only
        )
        return ab_tests
        
    except Exception as e:
        logger.error(f"Failed to get A/B tests: {e}")
        raise internal_server_exception("Failed to get A/B tests")


@router.get("/ab-tests/{test_id}", response_model=ABTestConfigResponse)
async def get_ab_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> ABTestConfigResponse:
    """
    Get specific A/B test configuration.
    
    Returns detailed information about an A/B test including
    performance metrics, participant allocation, and results.
    """
    try:
        ab_test = await flow_management.get_ab_test(test_id)
        return ab_test
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to get A/B test {test_id}: {e}")
        raise internal_server_exception("Failed to get A/B test")


@router.put("/ab-tests/{test_id}", response_model=ABTestConfigResponse)
async def update_ab_test(
    test_id: UUID,
    test_config: ABTestConfigRequest,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> ABTestConfigResponse:
    """
    Update A/B test configuration.
    
    Updates A/B test settings such as allocation percentages,
    success metrics, or test duration.
    """
    try:
        ab_test = await flow_management.update_ab_test(
            test_id=test_id,
            test_config=test_config,
            updated_by=current_user.id
        )
        return ab_test
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except ValidationError as e:
        raise flow_operation_exception("update_ab_test", str(e))
    except Exception as e:
        logger.error(f"Failed to update A/B test {test_id}: {e}")
        raise internal_server_exception("Failed to update A/B test")


@router.post("/ab-tests/{test_id}/stop", response_model=None)
async def stop_ab_test(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> dict[str, Any]:
    """
    Stop A/B test.
    
    Stops an active A/B test and finalizes results. Patients will
    continue with the winning variant or default flow.
    """
    try:
        results = await flow_management.stop_ab_test(
            test_id=test_id,
            stopped_by=current_user.id
        )
        return {
            "success": True,
            "message": "A/B test stopped successfully",
            "final_results": results
        }
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to stop A/B test {test_id}: {e}")
        raise internal_server_exception("Failed to stop A/B test")


@router.get("/ab-tests/{test_id}/results", response_model=None)
async def get_ab_test_results(
    test_id: UUID,
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
) -> dict[str, Any]:
    """
    Get A/B test results and analytics.
    
    Returns comprehensive results including statistical significance,
    conversion rates, engagement metrics, and recommendations.
    """
    try:
        results = await flow_management.get_ab_test_results(test_id)
        return {
            "success": True,
            "test_id": str(test_id),
            "results": results,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(f"ab_test_{test_id}")
    except Exception as e:
        logger.error(f"Failed to get A/B test results {test_id}: {e}")
        raise internal_server_exception("Failed to get A/B test results")


# Message Preview Endpoints
@router.post("/preview-message", response_model=None)
async def preview_flow_message(
    patient_id: UUID,
    template_id: UUID,
    day: int = Query(1, ge=1, description="Flow day to preview"),
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service)
) -> dict[str, Any]:
    """
    Preview AI-powered flow message for healthcare providers.
    
    Generates a preview of what message would be sent to a patient
    on a specific day using AI personalization, without actually
    sending the message.
    """
    try:
        preview = await flow_service.preview_flow_message(
            patient_id=patient_id,
            template_id=template_id,
            day=day
        )
        return {
            "success": True,
            "patient_id": str(patient_id),
            "template_id": str(template_id),
            "day": day,
            "preview": preview,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except FlowStateNotFoundError:
        raise flow_not_found_exception(str(patient_id))
    except Exception as e:
        logger.error(f"Failed to preview flow message: {e}")
        raise internal_server_exception("Failed to preview flow message")


# Health Check Endpoints
@router.get("/health/gemini", response_model=None)
async def check_gemini_health(
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service)
) -> dict[str, Any]:
    """
    Check Gemini AI integration health.
    
    Tests connectivity and functionality of the Gemini AI service
    used for message personalization and conversation memory.
    """
    try:
        health_status = await flow_service.check_gemini_health()
        return {
            "service": "gemini",
            "status": "healthy" if health_status else "unhealthy",
            "details": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")
        return {
            "service": "gemini",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }


@router.get("/health/redis", response_model=None)
async def check_redis_health(
    current_user: User = Depends(get_current_user),
    flow_service: FlowEngineIntegrationService = Depends(get_flow_service)
) -> dict[str, Any]:
    """
    Check Redis conversation memory health.
    
    Tests connectivity and functionality of the Redis service
    used for conversation memory and anti-repetition features.
    """
    try:
        health_status = await flow_service.check_redis_health()
        return {
            "service": "redis",
            "status": "healthy" if health_status else "unhealthy",
            "details": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "service": "redis",
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }


# Additional endpoints to address Frontend-v2 requirements

@router.get("", response_model=List[FlowStateResponse])
async def list_flows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
):
    """Get list of active flows for the current user's patients."""
    try:
        flows = await flow_management.list_user_flows(
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        return flows
    except Exception as e:
        logger.error(f"Error listing flows for user {current_user.id}: {e}")
        raise internal_server_exception("Failed to list flows")


@router.post("/start", response_model=FlowStateResponse)
async def start_flow(
    request: StartFlowRequest,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
):
    """Start a new flow for a patient."""
    # Verify patient exists and user has access
    patient = patient_service.get_patient(request.patient_id)
    if not patient:
        raise PatientNotFoundError(str(request.patient_id))

    if patient.doctor_id != current_user.id:
        raise PatientAccessDeniedError(str(request.patient_id))

    try:
        flow_state = await flow_management.start_patient_flow(
            patient_id=request.patient_id,
            flow_type=request.flow_type
        )
        return flow_state
    except FlowOperationError as e:
        raise flow_operation_exception("start_flow", str(e))
    except Exception as e:
        logger.error(f"Error starting flow for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to start flow")


@router.post("/{patient_id}/response", response_model=FlowAdvancementResponse)
async def process_patient_response(
    patient_id: UUID,
    request: ProcessResponseRequest,
    current_user: User = Depends(get_current_user),
    patient_service: PatientService = Depends(get_patient_service),
    flow_management: FlowManagementService = Depends(get_flow_management_service)
):
    """Process a patient's response and advance the flow accordingly."""
    # Verify patient exists and user has access
    patient = patient_service.get_patient(patient_id)
    if not patient:
        raise PatientNotFoundError(str(patient_id))

    if patient.doctor_id != current_user.id:
        raise PatientAccessDeniedError(str(patient_id))

    try:
        advancement = await flow_management.process_patient_response(
            patient_id=patient_id,
            response_text=request.response_text,
            response_metadata=request.response_metadata or {}
        )
        return advancement
    except FlowOperationError as e:
        raise flow_operation_exception("process_response", str(e))
    except Exception as e:
        logger.error(f"Error processing response for patient {patient_id}: {e}")
        raise internal_server_exception("Failed to process patient response")


@router.get("/analytics", response_model=FlowAnalyticsSchema)
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    flow_analytics: FlowAnalyticsService = Depends(get_flow_analytics_service)
):
    """Get a summary of flow analytics (alias for detailed analytics endpoints)."""
    try:
        # Aggregate data from various analytics endpoints
        analytics_data = await flow_analytics.get_comprehensive_analytics(
            user_id=current_user.id
        )
        return analytics_data
    except Exception as e:
        logger.error(f"Error getting analytics summary for user {current_user.id}: {e}")
        raise internal_server_exception("Failed to get analytics summary")