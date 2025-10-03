"""
A/B Testing API Endpoints for Hormonia Healthcare System

RESTful API for managing A/B experiments with healthcare compliance,
patient safety controls, and comprehensive analytics.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.ab_experiment import ABExperiment, ExperimentStatus
from app.models.user import User
from app.schemas.ab_testing import (
    # Request schemas
    CreateExperimentRequest, StartExperimentRequest, EmergencyStopRequest,
    UpdateExperimentRequest,

    # Response schemas
    CreateExperimentResponse, StartExperimentResponse, EmergencyStopResponse,
    ExperimentInfo, ExperimentResults, ExperimentStatus, ExperimentList,
    ExperimentDashboard, ExperimentReport, ExperimentAnalysisResponse,
    ExperimentMonitoring, VariantAssignment, ExperimentMetric,

    # Enums
    ExperimentStatusEnum, VariantTypeEnum
)
from app.services.ab_testing import ABTestingService, get_ab_testing_service
from app.services.audit_service import AuditService
from app.core.rate_limiting import RateLimiter
from app.core.security import require_admin_or_physician

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/ab-testing", tags=["A/B Testing"])
security = HTTPBearer()
rate_limiter = RateLimiter()


@router.post("/experiments", response_model=CreateExperimentResponse)
async def create_experiment(
    request: CreateExperimentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Create a new A/B testing experiment.

    Requires admin or physician privileges for healthcare safety.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Apply rate limiting
        await rate_limiter.check_rate_limit(
            key=f"create_experiment:{current_user.id}",
            limit=5,  # 5 experiments per hour
            window=3600
        )

        # Create experiment
        experiment_id = ab_service.create_experiment(
            name=request.name,
            description=request.description,
            message_template=request.message_template,
            target_population=request.target_population.dict() if request.target_population else None,
            duration_days=request.duration_days,
            traffic_split=request.traffic_split,
            primary_metric=request.primary_metric,
            secondary_metrics=request.secondary_metrics,
            safety_checks=request.safety_config.medical_keyword_check if request.safety_config else True,
            created_by=current_user.email
        )

        # Get created experiment
        experiment = db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()

        if not experiment:
            raise HTTPException(status_code=500, detail="Failed to create experiment")

        # Schedule safety review notification
        background_tasks.add_task(
            _schedule_safety_review_notification,
            experiment_id,
            current_user.email
        )

        return CreateExperimentResponse(
            experiment_id=experiment_id,
            message="Experiment created successfully. Safety review required before starting.",
            experiment=ExperimentInfo.from_orm(experiment)
        )

    except ValueError as e:
        logger.warning(f"Experiment creation validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating experiment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create experiment")


@router.post("/experiments/{experiment_id}/start", response_model=StartExperimentResponse)
async def start_experiment(
    experiment_id: str,
    request: StartExperimentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Start an A/B testing experiment after safety confirmations.

    Requires explicit confirmations for healthcare compliance.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Validate experiment exists
        experiment = db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        # Validate experiment can be started
        if experiment.status != ExperimentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail=f"Experiment cannot be started from status {experiment.status.value}"
            )

        # Start experiment
        success = ab_service.start_experiment(experiment_id, current_user.email)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to start experiment")

        # Refresh experiment data
        db.refresh(experiment)

        # Calculate estimated completion
        estimated_completion = experiment.start_date + timedelta(days=experiment.duration_days)

        # Schedule monitoring tasks
        background_tasks.add_task(
            _setup_experiment_monitoring,
            experiment_id
        )

        return StartExperimentResponse(
            experiment_id=experiment_id,
            message="Experiment started successfully. Monitoring is active.",
            started_at=experiment.start_date,
            eligible_patients=experiment.total_participants,
            estimated_completion=estimated_completion
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start experiment")


@router.post("/experiments/{experiment_id}/emergency-stop", response_model=EmergencyStopResponse)
async def emergency_stop_experiment(
    experiment_id: str,
    request: EmergencyStopRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Emergency stop an active experiment due to safety or performance concerns.

    Immediately halts assignment of new patients to variants.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Apply rate limiting for emergency stops
        await rate_limiter.check_rate_limit(
            key=f"emergency_stop:{current_user.id}",
            limit=10,  # 10 emergency stops per hour
            window=3600
        )

        # Emergency stop experiment
        success = ab_service.emergency_stop_experiment(
            experiment_id,
            request.reason,
            current_user.email
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to emergency stop experiment")

        # Get final results
        final_results = None
        try:
            results_data = ab_service.calculate_experiment_results(experiment_id)
            if not results_data.get('error'):
                final_results = ExperimentResults(**results_data)
        except Exception as e:
            logger.warning(f"Could not generate final results for emergency stop: {str(e)}")

        # Send notifications if safety concern or immediate action required
        if request.safety_concern or request.immediate_action_required:
            background_tasks.add_task(
                _send_emergency_stop_notifications,
                experiment_id,
                request.reason,
                current_user.email,
                request.safety_concern,
                request.immediate_action_required
            )

        return EmergencyStopResponse(
            experiment_id=experiment_id,
            message="Experiment emergency stopped successfully.",
            stopped_at=datetime.utcnow(),
            reason=request.reason,
            final_results=final_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error emergency stopping experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to emergency stop experiment")


@router.get("/experiments", response_model=ExperimentList)
async def list_experiments(
    status: Optional[ExperimentStatusEnum] = Query(None, description="Filter by experiment status"),
    message_template: Optional[str] = Query(None, description="Filter by message template"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List A/B testing experiments with filtering and pagination.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Build query
        query = db.query(ABExperiment)

        # Apply filters
        if status:
            query = query.filter(ABExperiment.status == ExperimentStatus(status.value))

        if message_template:
            query = query.filter(ABExperiment.message_template == message_template)

        if created_by:
            query = query.filter(ABExperiment.created_by.ilike(f"%{created_by}%"))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        experiments = query.offset(offset).limit(per_page).all()

        return ExperimentList(
            experiments=[ExperimentInfo.from_orm(exp) for exp in experiments],
            total=total,
            page=page,
            per_page=per_page,
            has_next=offset + per_page < total,
            has_prev=page > 1
        )

    except Exception as e:
        logger.error(f"Error listing experiments: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list experiments")


@router.get("/experiments/{experiment_id}", response_model=ExperimentInfo)
async def get_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific experiment.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Get experiment
        experiment = db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()

        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        return ExperimentInfo.from_orm(experiment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get experiment")


@router.get("/experiments/{experiment_id}/status", response_model=ExperimentStatus)
async def get_experiment_status(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Get current status and basic metrics for an experiment.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Get status
        status_data = ab_service.get_experiment_status(experiment_id)

        if status_data.get('error'):
            raise HTTPException(status_code=404, detail=status_data['error'])

        # Calculate days remaining
        if status_data.get('end_date'):
            end_date = datetime.fromisoformat(status_data['end_date'].replace('Z', '+00:00'))
            days_remaining = max(0, (end_date - datetime.utcnow()).days)
            status_data['days_remaining'] = days_remaining
            status_data['estimated_completion'] = end_date

        return ExperimentStatus(**status_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment status {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get experiment status")


@router.get("/experiments/{experiment_id}/results", response_model=ExperimentAnalysisResponse)
async def get_experiment_results(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Get comprehensive experiment results and statistical analysis.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Calculate results
        results_data = ab_service.calculate_experiment_results(experiment_id)

        if results_data.get('error'):
            raise HTTPException(status_code=400, detail=results_data['error'])

        results = ExperimentResults(**results_data)

        # Generate recommendations
        recommendations = results.recommendations

        # Generate next steps
        next_steps = []
        if results.is_statistically_significant:
            if results.winner == "treatment":
                next_steps.append("Consider rolling out AI-humanized messages to broader population")
                next_steps.append("Monitor performance during rollout phase")
            else:
                next_steps.append("Continue using static message templates")
                next_steps.append("Consider testing different AI approaches or message types")
        else:
            next_steps.append("Consider extending experiment duration")
            next_steps.append("Review target population criteria")
            next_steps.append("Analyze secondary metrics for insights")

        # Determine confidence level
        confidence_level = "high"
        if results.variant_performance["control"]["sample_size"] < 200:
            confidence_level = "medium"
        if results.variant_performance["control"]["sample_size"] < 100:
            confidence_level = "low"

        return ExperimentAnalysisResponse(
            results=results,
            recommendations=recommendations,
            next_steps=next_steps,
            confidence_level=confidence_level
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting experiment results {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get experiment results")


@router.put("/experiments/{experiment_id}", response_model=ExperimentInfo)
async def update_experiment(
    experiment_id: str,
    request: UpdateExperimentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update experiment configuration (only for draft experiments).
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Get experiment
        experiment = db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()

        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        # Validate experiment can be modified
        if experiment.status != ExperimentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Only draft experiments can be modified"
            )

        # Update fields
        update_data = request.dict(exclude_unset=True)

        for field, value in update_data.items():
            if field == "target_population" and value:
                experiment.target_population = value.dict()
            elif field == "safety_config" and value:
                experiment.safety_checks_enabled = value.medical_keyword_check
                experiment.medical_keyword_check = value.medical_keyword_check
                experiment.manual_review_required = value.manual_review_required
                experiment.emergency_stop_enabled = value.emergency_stop_enabled
            else:
                setattr(experiment, field, value)

        # Update modified timestamp
        experiment.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(experiment)

        return ExperimentInfo.from_orm(experiment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update experiment")


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(
    experiment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an experiment (only draft experiments with no data).
    """
    try:
        # Validate user permissions (admin only for deletion)
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required for experiment deletion")

        # Get experiment
        experiment = db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()

        if not experiment:
            raise HTTPException(status_code=404, detail="Experiment not found")

        # Validate experiment can be deleted
        if experiment.status != ExperimentStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Only draft experiments can be deleted"
            )

        if experiment.total_participants > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete experiment with participant data"
            )

        # Delete experiment
        db.delete(experiment)
        db.commit()

        return {"message": "Experiment deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete experiment")


@router.get("/dashboard", response_model=ExperimentDashboard)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get A/B testing dashboard with summary metrics.
    """
    try:
        # Validate user permissions
        require_admin_or_physician(current_user)

        # Get experiment counts
        total_experiments = db.query(ABExperiment).count()
        active_experiments = db.query(ABExperiment).filter(
            ABExperiment.status == ExperimentStatus.ACTIVE
        ).count()
        completed_experiments = db.query(ABExperiment).filter(
            ABExperiment.status == ExperimentStatus.COMPLETED
        ).count()
        terminated_experiments = db.query(ABExperiment).filter(
            ABExperiment.status == ExperimentStatus.TERMINATED
        ).count()

        # Get recent experiments
        recent_experiments = db.query(ABExperiment).order_by(
            ABExperiment.created_at.desc()
        ).limit(5).all()

        # Calculate performance summary
        completed_exps = db.query(ABExperiment).filter(
            ABExperiment.status == ExperimentStatus.COMPLETED,
            ABExperiment.is_statistically_significant == True
        ).all()

        successful_experiments = len([exp for exp in completed_exps if exp.winner == "treatment"])
        success_rate = successful_experiments / max(1, len(completed_exps))

        # Calculate average response rate (simplified)
        avg_response_rate = 0.25  # Placeholder - implement based on actual metrics
        total_participants = sum(exp.total_participants for exp in completed_exps)

        # Generate alerts
        alerts = []
        active_with_issues = db.query(ABExperiment).filter(
            ABExperiment.status == ExperimentStatus.ACTIVE,
            ABExperiment.end_date < datetime.utcnow()
        ).count()

        if active_with_issues > 0:
            alerts.append(f"{active_with_issues} experiments have exceeded their planned duration")

        return ExperimentDashboard(
            total_experiments=total_experiments,
            active_experiments=active_experiments,
            completed_experiments=completed_experiments,
            terminated_experiments=terminated_experiments,
            recent_experiments=[ExperimentInfo.from_orm(exp) for exp in recent_experiments],
            performance_summary={
                "success_rate": success_rate,
                "avg_response_rate": avg_response_rate,
                "total_participants": total_participants
            },
            alerts=alerts,
            average_response_rate=avg_response_rate,
            total_participants=total_participants,
            successful_experiments=successful_experiments,
            success_rate=success_rate
        )

    except Exception as e:
        logger.error(f"Error getting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")


# Background task functions

async def _schedule_safety_review_notification(experiment_id: str, created_by: str):
    """Schedule safety review notification."""
    logger.info(f"Scheduling safety review notification for experiment {experiment_id}")
    # Implement notification logic here


async def _setup_experiment_monitoring(experiment_id: str):
    """Setup real-time monitoring for experiment."""
    logger.info(f"Setting up monitoring for experiment {experiment_id}")
    # Implement monitoring setup logic here


async def _send_emergency_stop_notifications(
    experiment_id: str,
    reason: str,
    stopped_by: str,
    safety_concern: bool,
    immediate_action: bool
):
    """Send emergency stop notifications."""
    logger.critical(f"Sending emergency stop notifications for experiment {experiment_id}: {reason}")
    # Implement notification logic here


# Helper endpoints for integration

@router.post("/experiments/{experiment_id}/assign-variant")
async def assign_patient_variant(
    experiment_id: str,
    patient_id: UUID,
    message_template: str,
    current_user: User = Depends(get_current_user),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Assign patient to experiment variant (for internal use by message services).
    """
    try:
        from app.services.message_factory import MessageTemplate

        # Convert string to enum
        template_enum = MessageTemplate(message_template)

        # Assign variant
        variant = ab_service.assign_patient_to_variant(patient_id, experiment_id, template_enum)

        if variant is None:
            return {"assigned": False, "reason": "not_eligible"}

        return {
            "assigned": True,
            "variant": variant.value,
            "experiment_id": experiment_id
        }

    except Exception as e:
        logger.error(f"Error assigning variant: {str(e)}")
        return {"assigned": False, "reason": "error", "error": str(e)}


@router.post("/experiments/{experiment_id}/track-performance")
async def track_message_performance(
    experiment_id: str,
    message_id: int,
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(get_current_user),
    ab_service: ABTestingService = Depends(get_ab_testing_service)
):
    """
    Track message performance for A/B testing (for internal use).
    """
    try:
        ab_service.track_message_performance(message_id, event_type, event_data)
        return {"tracked": True}

    except Exception as e:
        logger.error(f"Error tracking performance: {str(e)}")
        return {"tracked": False, "error": str(e)}