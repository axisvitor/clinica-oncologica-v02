"""
A/B Testing Service
Business logic for A/B testing, experiment management, and statistical analysis.
"""

import io
import csv
import json
import hashlib
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID, uuid4

import numpy as np
from scipy import stats as scipy_stats
from sqlalchemy.orm import  joinedload
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status, BackgroundTasks

from app.models.user import User, UserRole
from app.models.ab_experiment import (
    ABExperiment,
    ABVariantAssignment,
    ABExperimentMetric,
    ExperimentStatus as ModelExperimentStatus,
    VariantType as ModelVariantType,
)
from app.schemas.v2.ab_testing import (
    ExperimentCreate,
    ExperimentUpdate,
    VariantAssignmentResponse,
    ConversionEventCreate,
    ConversionEventResponse,
    ExperimentResults,
    ExperimentStatistics,
    VariantPerformance,
    StatisticalTestResult,
    ConfidenceInterval,
    WinnerDeclarationRequest,
    WinnerDeclarationResponse,
    ExportFormat,
    ExportResponse,
    SampleSizeCalculationRequest,
    SampleSizeCalculationResponse,
    ExperimentDashboard,
    ExperimentStatus,
    VariantType,
    StatisticalTest,
    ConfidenceLevel,
)
from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger
from app.api.v2.dependencies import create_cursor, get_pagination_params

logger = get_logger(__name__)

# Cache TTLs
ACTIVE_EXPERIMENTS_CACHE_TTL = 300
EXPERIMENT_RESULTS_CACHE_TTL = 900
DASHBOARD_CACHE_TTL = 300

class ABTestingService:
    """Service for A/B testing operations."""

    def __init__(self, db: Any):
        self.db = db

    async def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return None
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            return None
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    async def _set_cached_result(self, cache_key: str, data: Any, ttl: int) -> None:
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return
            
            if hasattr(data, 'model_dump'):
                serialized = json.dumps(data.model_dump(), default=str)
            elif hasattr(data, 'dict'):
                serialized = json.dumps(data.dict(), default=str)
            else:
                serialized = json.dumps(data, default=str)
                
            await redis_client.setex(cache_key, ttl, serialized)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    async def _invalidate_cache_pattern(self, pattern: str) -> None:
        try:
            redis_client = await get_async_redis()
            if redis_client is None:
                return
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")

    def _get_cache_key(self, endpoint: str, **params) -> str:
        param_str = json.dumps(params, sort_keys=True, default=str)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"ab_testing:v2:{endpoint}:{param_hash}"

    def _serialize_experiment(self, exp: ABExperiment) -> dict:
        return {
            "id": exp.id,
            "name": exp.name,
            "description": exp.description,
            "hypothesis": getattr(exp, "hypothesis", None),
            "status": exp.status.value if hasattr(exp.status, "value") else str(exp.status),
            "created_at": exp.created_at,
            "updated_at": exp.updated_at,
            "created_by": UUID(exp.created_by) if exp.created_by else None,
            "variants": json.loads(exp.statistical_config.get("variants", "[]")) if exp.statistical_config else [],
            "conversion_goals": json.loads(exp.statistical_config.get("goals", "[]")) if exp.statistical_config else [],
            "start_date": exp.start_date,
            "end_date": exp.end_date,
            "max_duration_days": exp.duration_days,
            "total_participants": exp.total_participants,
            "total_conversions": getattr(exp, "total_conversions", 0),
            "statistical_config": exp.statistical_config or {},
            "winner_decision_mode": getattr(exp, "winner_decision_mode", "manual"),
            "winner": exp.winner,
            "winner_declared_at": getattr(exp, "winner_declared_at", None),
            "winner_confidence": getattr(exp, "winner_confidence", None),
        }

    def _calculate_confidence_interval(self, conversion_rate: float, sample_size: int, confidence_level: float = 0.95) -> ConfidenceInterval:
        if sample_size == 0:
            return ConfidenceInterval(lower_bound=0.0, upper_bound=0.0, confidence_level=confidence_level, margin_of_error=0.0)

        z_score = scipy_stats.norm.ppf((1 + confidence_level) / 2)
        p = conversion_rate
        n = sample_size

        denominator = 1 + z_score**2 / n
        centre_adjusted_probability = (p + z_score**2 / (2 * n)) / denominator
        adjusted_standard_error = np.sqrt((p * (1 - p) / n + z_score**2 / (4 * n**2))) / denominator

        lower = centre_adjusted_probability - z_score * adjusted_standard_error
        upper = centre_adjusted_probability + z_score * adjusted_standard_error
        margin = (upper - lower) / 2

        return ConfidenceInterval(
            lower_bound=max(0.0, lower),
            upper_bound=min(1.0, upper),
            confidence_level=confidence_level,
            margin_of_error=margin
        )

    def _perform_chi_square_test(self, control_conv: int, control_total: int, treat_conv: int, treat_total: int, alpha: float = 0.05) -> StatisticalTestResult:
        observed = np.array([
            [control_conv, control_total - control_conv],
            [treat_conv, treat_total - treat_conv]
        ])
        chi2, p_value, dof, expected = scipy_stats.chi2_contingency(observed)
        n = control_total + treat_total
        effect_size = np.sqrt(chi2 / n)
        
        interpretation = "negligible"
        if effect_size >= 0.5: interpretation = "large"
        elif effect_size >= 0.3: interpretation = "medium"
        elif effect_size >= 0.1: interpretation = "small"

        return StatisticalTestResult(
            test_type=StatisticalTest.CHI_SQUARE,
            test_statistic=float(chi2),
            p_value=float(p_value),
            is_significant=p_value < alpha,
            alpha=alpha,
            degrees_of_freedom=int(dof),
            effect_size=float(effect_size),
            effect_size_interpretation=interpretation
        )

    def _weighted_random_assignment(self, variants: List[Dict], user_hash: str) -> str:
        random.seed(int(hashlib.md5(user_hash.encode()).hexdigest(), 16))
        weights = [v["traffic_weight"] for v in variants]
        variant_types = [v["type"] for v in variants]
        return random.choices(variant_types, weights=weights, k=1)[0]

    async def list_experiments(self, cursor: Optional[str], limit: int, status: Optional[ExperimentStatus], search: Optional[str]) -> Dict[str, Any]:
        cache_key = self._get_cache_key("list_experiments", cursor=cursor, limit=limit, status=status, search=search)
        cached = await self._get_cached_result(cache_key)
        if cached: return cached

        pagination = get_pagination_params(cursor, limit)
        cursor_data = pagination["cursor_data"]

        query = self.db.query(ABExperiment).options(joinedload(ABExperiment.variant_assignments))
        if cursor_data:
            query = query.filter(ABExperiment.id > cursor_data.get("id"))
        if status:
            query = query.filter(ABExperiment.status == ModelExperimentStatus[status.value.upper()])
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(or_(ABExperiment.name.ilike(search_pattern), ABExperiment.description.ilike(search_pattern)))

        query = query.order_by(ABExperiment.id)
        experiments = query.limit(limit + 1).all()

        has_more = len(experiments) > limit
        if has_more: experiments = experiments[:limit]
        
        next_cursor = create_cursor(experiments[-1].id) if has_more and experiments else None
        data = [self._serialize_experiment(exp) for exp in experiments]
        
        result = {"data": data, "next_cursor": next_cursor, "has_more": has_more, "total": None}
        await self._set_cached_result(cache_key, result, ACTIVE_EXPERIMENTS_CACHE_TTL)
        return result

    async def get_experiment(self, experiment_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key("get_experiment", experiment_id=str(experiment_id))
        cached = await self._get_cached_result(cache_key)
        if cached: return cached

        experiment = self.db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")

        result = self._serialize_experiment(experiment)
        await self._set_cached_result(cache_key, result, ACTIVE_EXPERIMENTS_CACHE_TTL)
        return result

    async def create_experiment(self, data: ExperimentCreate, user_id: Optional[UUID]) -> Dict[str, Any]:
        experiment = ABExperiment(
            id=uuid4(),
            name=data.name,
            description=data.description,
            status=ModelExperimentStatus.DRAFT,
            duration_days=data.max_duration_days,
            traffic_split=data.variants[1].traffic_weight if len(data.variants) >= 2 else 0.5,
            primary_metric="conversion_rate",
            created_by=str(user_id) if user_id else "system",
            start_date=data.start_date,
            end_date=data.end_date,
            statistical_config={
                "variants": [v.dict() for v in data.variants],
                "goals": [g.dict() for g in data.conversion_goals],
                "statistical_config": data.statistical_config.dict(),
                "winner_decision_mode": data.winner_decision_mode.value,
                "auto_declare_threshold": data.auto_declare_threshold,
                "hypothesis": data.hypothesis,
            },
        )
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        await self._invalidate_cache_pattern("ab_testing:v2:list_experiments:*")
        return self._serialize_experiment(experiment)

    async def update_experiment(self, experiment_id: UUID, data: ExperimentUpdate) -> Dict[str, Any]:
        experiment = self.db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment: raise HTTPException(status_code=404, detail="Not found")
        if experiment.status != ModelExperimentStatus.DRAFT: raise HTTPException(status_code=400, detail="Only draft can be updated")

        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if field == "statistical_config" and value:
                current = experiment.statistical_config or {}
                current.update(value.dict())
                experiment.statistical_config = current
            elif hasattr(experiment, field):
                setattr(experiment, field, value)
        
        experiment.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(experiment)
        await self._invalidate_cache_pattern(f"ab_testing:v2:*experiment*{experiment_id}*")
        return self._serialize_experiment(experiment)

    async def assign_variant(self, experiment_id: UUID, user_id: Optional[str], anonymous_id: str, force_variant: Optional[VariantType]) -> VariantAssignmentResponse:
        experiment = self.db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment: raise HTTPException(status_code=404, detail="Experiment not found")
        if experiment.status != ModelExperimentStatus.ACTIVE: raise HTTPException(status_code=400, detail="Experiment not active")

        user_identifier = user_id if user_id else anonymous_id
        hashed_id = hashlib.sha256(user_identifier.encode()).hexdigest()[:32]

        existing = self.db.query(ABVariantAssignment).filter(
            and_(ABVariantAssignment.experiment_id == experiment_id, ABVariantAssignment.anonymous_patient_id == hashed_id)
        ).first()

        variants = json.loads(experiment.statistical_config.get("variants", "[]"))

        if existing:
            variant_data = next((v for v in variants if v["type"] == existing.variant.value), {})
            return VariantAssignmentResponse(
                experiment_id=experiment_id,
                variant_type=VariantType(existing.variant.value),
                variant_name=variant_data.get("name", existing.variant.value),
                variant_configuration=variant_data.get("configuration", {}),
                assigned_at=existing.assigned_at,
                is_eligible=True,
                assignment_reason="existing_assignment"
            )

        assigned_variant = force_variant.value if force_variant else self._weighted_random_assignment(variants, user_identifier)
        assignment = ABVariantAssignment(
            id=uuid4(),
            experiment_id=experiment_id,
            anonymous_patient_id=hashed_id,
            variant=ModelVariantType[assigned_variant.upper()],
            assignment_hash=hashlib.sha256(f"{experiment_id}{user_identifier}{assigned_variant}".encode()).hexdigest(),
            assignment_reason="weighted_randomization",
            assigned_at=datetime.utcnow()
        )
        self.db.add(assignment)
        
        experiment.total_participants += 1
        if assigned_variant == "control": experiment.control_participants += 1
        else: experiment.treatment_participants += 1
        
        self.db.commit()
        
        variant_data = next((v for v in variants if v["type"] == assigned_variant), {})
        return VariantAssignmentResponse(
            experiment_id=experiment_id,
            variant_type=VariantType(assigned_variant),
            variant_name=variant_data.get("name", assigned_variant),
            variant_configuration=variant_data.get("configuration", {}),
            assigned_at=datetime.utcnow(),
            is_eligible=True,
            assignment_reason="weighted_randomization"
        )

    async def track_conversion(self, data: ConversionEventCreate) -> ConversionEventResponse:
        user_identifier = str(data.user_id) if data.user_id else data.anonymous_id
        anonymous_id = hashlib.sha256(user_identifier.encode()).hexdigest()[:32]

        metric = ABExperimentMetric(
            id=uuid4(),
            experiment_id=data.experiment_id,
            anonymous_patient_id=anonymous_id,
            variant=ModelVariantType[data.variant_type.value.upper()],
            event_type=data.goal_type.value,
            event_data={"goal_name": data.goal_name, "value": data.value, "metadata": data.metadata},
            event_timestamp=data.timestamp or datetime.utcnow(),
            processed=False,
            included_in_analysis=True
        )
        self.db.add(metric)
        self.db.commit()
        await self._invalidate_cache_pattern(f"ab_testing:v2:*results*{data.experiment_id}*")
        
        return ConversionEventResponse(
            id=metric.id,
            experiment_id=data.experiment_id,
            variant_type=data.variant_type,
            goal_name=data.goal_name,
            goal_type=data.goal_type,
            value=data.value,
            recorded_at=metric.event_timestamp
        )

    async def get_experiment_results(self, experiment_id: UUID, confidence_level: ConfidenceLevel) -> ExperimentResults:
        cache_key = self._get_cache_key("get_results", experiment_id=str(experiment_id), confidence_level=confidence_level)
        cached = await self._get_cached_result(cache_key)
        if cached: return ExperimentResults(**cached)

        experiment = self.db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment: raise HTTPException(status_code=404, detail="Not found")

        # Fetch Data
        assignments = self.db.query(ABVariantAssignment).filter(ABVariantAssignment.experiment_id == experiment_id).all()
        metrics = self.db.query(ABExperimentMetric).filter(and_(ABExperimentMetric.experiment_id == experiment_id, ABExperimentMetric.included_in_analysis == True)).all()

        variant_stats = {}
        for a in assignments:
            v = a.variant.value
            if v not in variant_stats: variant_stats[v] = {"total": 0, "conversions": 0}
            variant_stats[v]["total"] += 1
        
        for m in metrics:
            v = m.variant.value
            if v in variant_stats: variant_stats[v]["conversions"] += 1

        variant_performances = []
        for v_type, stats in variant_stats.items():
            conv_rate = stats["conversions"] / stats["total"] if stats["total"] > 0 else 0
            ci = self._calculate_confidence_interval(conv_rate, stats["total"], float(confidence_level.value)/100)
            variant_performances.append(VariantPerformance(
                variant_type=VariantType(v_type),
                variant_name=v_type.title(),
                sample_size=stats["total"],
                conversion_rate=conv_rate,
                conversions=stats["conversions"],
                views=stats["total"],
                confidence_interval={"lower": ci.lower_bound, "upper": ci.upper_bound, "margin": ci.margin_of_error},
                avg_engagement_time=None, error_rate=0.0
            ))

        # Stat Test
        test_result = None
        winner, winner_conf = None, None
        if len(variant_stats) >= 2:
            ctrl = variant_stats.get("control", {"total": 0, "conversions": 0})
            trt = variant_stats.get("treatment", {"total": 0, "conversions": 0})
            if ctrl["total"] > 0 and trt["total"] > 0:
                test_result = self._perform_chi_square_test(ctrl["conversions"], ctrl["total"], trt["conversions"], trt["total"])
                winner = "treatment" if trt["conversions"]/trt["total"] > ctrl["conversions"]/ctrl["total"] else "control"
                winner_conf = 1 - test_result.p_value

        start = experiment.start_date or experiment.created_at
        end = experiment.end_date or datetime.utcnow()
        
        result = ExperimentResults(
            experiment_id=experiment_id,
            experiment_name=experiment.name,
            status=ExperimentStatus(experiment.status.value),
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            duration_days=(end - start).days,
            statistics=ExperimentStatistics(
                total_participants=sum(s["total"] for s in variant_stats.values()),
                total_conversions=sum(s["conversions"] for s in variant_stats.values()),
                overall_conversion_rate=0, # Simplified
                variants=variant_performances,
                statistical_test=test_result,
                winner=VariantType(winner) if winner else None,
                winner_confidence=winner_conf
            ),
            variant_details=variant_performances,
            goals_performance={},
            analyzed_at=datetime.utcnow(),
            recommendations=[],
            confidence_level=float(confidence_level.value)/100,
            is_conclusive=test_result.is_significant if test_result else False
        )
        
        await self._set_cached_result(cache_key, result, EXPERIMENT_RESULTS_CACHE_TTL)
        return result

    async def declare_winner(self, experiment_id: UUID, data: WinnerDeclarationRequest, user_id: Optional[UUID]) -> WinnerDeclarationResponse:
        experiment = self.db.query(ABExperiment).filter(ABExperiment.id == experiment_id).first()
        if not experiment: raise HTTPException(status_code=404, detail="Not found")
        if experiment.status not in [ModelExperimentStatus.ACTIVE, ModelExperimentStatus.COMPLETED]:
            raise HTTPException(status_code=400, detail="Invalid status")

        experiment.winner = data.winner_variant.value
        experiment.status = ModelExperimentStatus.COMPLETED
        experiment.end_date = datetime.utcnow()
        
        config = experiment.statistical_config or {}
        config.update({
            "winner_declared_at": datetime.utcnow().isoformat(),
            "winner_declared_by": str(user_id) if user_id else "system",
            "winner_confidence": data.confidence,
            "winner_notes": data.notes
        })
        experiment.statistical_config = config
        
        self.db.commit()
        await self._invalidate_cache_pattern(f"ab_testing:v2:*")
        
        return WinnerDeclarationResponse(
            experiment_id=experiment_id,
            winner_variant=data.winner_variant,
            confidence=data.confidence,
            declared_at=datetime.utcnow(),
            declared_by=user_id or UUID("00000000-0000-0000-0000-000000000000"),
            status_change=ExperimentStatus.COMPLETED,
            rollout_recommendation=f"Rollout {data.winner_variant.value}"
        )

    async def get_dashboard(self) -> ExperimentDashboard:
        cache_key = self._get_cache_key("dashboard")
        cached = await self._get_cached_result(cache_key)
        if cached: return ExperimentDashboard(**cached)

        total = self.db.query(ABExperiment).count()
        active = self.db.query(ABExperiment).filter(ABExperiment.status == ModelExperimentStatus.ACTIVE).count()
        completed = self.db.query(ABExperiment).filter(ABExperiment.status == ModelExperimentStatus.COMPLETED).count()
        draft = self.db.query(ABExperiment).filter(ABExperiment.status == ModelExperimentStatus.DRAFT).count()
        
        recent = self.db.query(ABExperiment).order_by(ABExperiment.created_at.desc()).limit(5).all()
        recent_exps = [self._serialize_experiment(exp) for exp in recent]
        
        total_participants = self.db.query(func.sum(ABExperiment.total_participants)).scalar() or 0
        total_conversions = self.db.query(ABExperimentMetric).filter(ABExperimentMetric.included_in_analysis == True).count()
        
        result = ExperimentDashboard(
            total_experiments=total,
            active_experiments=active,
            completed_experiments=completed,
            draft_experiments=draft,
            recent_experiments=recent_exps,
            total_participants_all_time=int(total_participants),
            total_conversions_all_time=total_conversions,
            avg_conversion_rate=total_conversions/total_participants if total_participants > 0 else 0,
            experiments_with_winner=0,
            avg_confidence_level=0.95,
            experiments_needing_review=0,
            experiments_ready_for_winner=0
        )
        
        await self._set_cached_result(cache_key, result, DASHBOARD_CACHE_TTL)
        return result
