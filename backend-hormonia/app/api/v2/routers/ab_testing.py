"""
A/B Testing API v2
Advanced A/B testing with statistical analysis, variant management, and conversion tracking.
Delegates logic to ABTestingService.
"""

from typing import Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.database import get_db
from app.dependencies.auth_dependencies import get_current_user_from_session
from app.schemas.v2.ab_testing import (
    ExperimentListResponse, ExperimentResponse, ExperimentCreate, ExperimentUpdate,
    VariantAssignmentResponse, VariantAssignmentRequest, ConversionEventCreate,
    ConversionEventResponse, ExperimentResults, WinnerDeclarationResponse,
    WinnerDeclarationRequest, ExperimentDashboard, ExperimentStatus, ConfidenceLevel
)
from app.services.ab_testing_service import ABTestingService
from app.utils.rate_limiter import limiter
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

RATE_LIMIT_READ = "40/minute"
RATE_LIMIT_WRITE = "20/minute"
RATE_LIMIT_ANALYSIS = "30/minute"

def get_ab_testing_service(db = Depends(get_db)) -> ABTestingService:
    return ABTestingService(db)

@router.get("/experiments", response_model=ExperimentListResponse)
@limiter.limit(RATE_LIMIT_READ)
async def list_experiments(
    request: Request,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[ExperimentStatus] = Query(None),
    search: Optional[str] = Query(None),
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.list_experiments(cursor, limit, status, search)

@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
@limiter.limit(RATE_LIMIT_READ)
async def get_experiment(
    request: Request,
    experiment_id: UUID,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.get_experiment(experiment_id)

@router.post("/experiments", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_WRITE)
async def create_experiment(
    request: Request,
    data: ExperimentCreate,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    user_id = current_user.get("id")
    return await service.create_experiment(data, user_id)

@router.patch("/experiments/{experiment_id}", response_model=ExperimentResponse)
@limiter.limit(RATE_LIMIT_WRITE)
async def update_experiment(
    request: Request,
    experiment_id: UUID,
    data: ExperimentUpdate,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.update_experiment(experiment_id, data)

@router.post("/experiments/{experiment_id}/assign", response_model=VariantAssignmentResponse)
@limiter.limit(RATE_LIMIT_WRITE)
async def assign_variant(
    request: Request,
    experiment_id: UUID,
    data: VariantAssignmentRequest,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.assign_variant(experiment_id, data.user_id, data.anonymous_id, data.force_variant)

@router.post("/experiments/conversions", response_model=ConversionEventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_WRITE)
async def track_conversion(
    request: Request,
    data: ConversionEventCreate,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.track_conversion(data)

@router.get("/experiments/{experiment_id}/results", response_model=ExperimentResults)
@limiter.limit(RATE_LIMIT_ANALYSIS)
async def get_experiment_results(
    request: Request,
    experiment_id: UUID,
    confidence_level: Optional[ConfidenceLevel] = Query(ConfidenceLevel.NINETY_FIVE),
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.get_experiment_results(experiment_id, confidence_level)

@router.post("/experiments/{experiment_id}/declare-winner", response_model=WinnerDeclarationResponse)
@limiter.limit(RATE_LIMIT_WRITE)
async def declare_winner(
    request: Request,
    experiment_id: UUID,
    data: WinnerDeclarationRequest,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.declare_winner(experiment_id, data, current_user.get("id"))

@router.get("/dashboard", response_model=ExperimentDashboard)
@limiter.limit(RATE_LIMIT_READ)
async def get_dashboard(
    request: Request,
    service: ABTestingService = Depends(get_ab_testing_service),
    current_user: dict = Depends(get_current_user_from_session)
):
    return await service.get_dashboard()
