"""
Enhanced Reports Service
Business logic for advanced reporting, custom builders, and scheduled delivery.
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from fastapi import HTTPException, BackgroundTasks

from app.models.user import UserRole
from app.schemas.v2.enhanced_reports import (
    ReportBuilderCreate,
    VisualizationCreate,
    VisualizationType,
    DeliveryConfigCreate,
    ReportShareCreate,
    PublicLinkCreate,
    MultiFormatExportRequest,
    ReportRestoreRequest,
    DashboardCreate,
    DashboardUpdate,
    DashboardSnapshotCreate,
)
from app.core.redis_unified import get_async_redis
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Cache TTLs
TEMPLATE_CACHE_TTL = 3600
REPORT_CACHE_TTL = 1800
SCHEDULED_CACHE_TTL = 600
DASHBOARD_CACHE_TTL = 300


class EnhancedReportsService:
    """Service for enhanced reporting operations."""

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

            if hasattr(data, "dict"):
                serialized = json.dumps(data.dict(), default=str)
            elif hasattr(data, "model_dump"):
                serialized = json.dumps(data.model_dump(), default=str)
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
        return f"enhanced_reports:v2:{endpoint}:{param_hash}"

    def _check_report_access(
        self, role: UserRole, user_id: UUID, report_id: UUID
    ) -> bool:
        if role == UserRole.ADMIN:
            return True
        # Mock implementation for now
        return True

    def _normalize_export_response(
        self,
        data: Dict[str, Any],
        export_id: Optional[UUID] = None,
        report_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        normalized = dict(data)
        if export_id and "export_id" not in normalized:
            normalized["export_id"] = str(export_id)
        if report_id and "report_id" not in normalized:
            normalized["report_id"] = str(report_id)
        normalized.setdefault("download_urls", {})
        normalized.setdefault("file_sizes", {})
        normalized.setdefault(
            "expires_at", (now + timedelta(days=1)).isoformat()
        )
        normalized.setdefault("created_at", now.isoformat())
        return normalized

    def _normalize_dashboard_response(
        self,
        data: Dict[str, Any],
        user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        normalized = dict(data)
        normalized.setdefault("layout", "grid")
        normalized.setdefault("widgets", [])
        normalized.setdefault("auto_refresh", False)
        normalized.setdefault("refresh_interval_seconds", 60)
        normalized.setdefault("is_public", False)
        normalized.setdefault("shared_with", None)
        normalized.setdefault("theme", "light")
        normalized.setdefault("view_count", 0)
        normalized.setdefault("created_at", now.isoformat())
        normalized.setdefault("updated_at", now.isoformat())
        if user_id:
            normalized.setdefault("created_by", str(user_id))
        return normalized

    async def build_custom_report(
        self,
        data: ReportBuilderCreate,
        user_id: UUID,
        background_tasks: BackgroundTasks,
    ) -> Dict[str, Any]:
        valid_data_sources = {
            "patients",
            "messages",
            "quizzes",
            "quiz_sessions",
            "flows",
        }
        for field in data.fields:
            if field.data_source not in valid_data_sources:
                raise HTTPException(
                    status_code=400, detail=f"Invalid data source: {field.data_source}"
                )

        builder_id = uuid4()

        # Background processing simulation
        # In a real service, this logic might be in a separate method or celery task
        # For now, we'll structure the response immediately

        response = {
            "id": str(builder_id),
            "name": data.name,
            "description": data.description,
            "fields": [f.dict() for f in data.fields],
            "filters": data.filters,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
            "row_count": 0,
            "generation_time_seconds": 0.0,
            "download_url": f"/api/v2/enhanced-reports/builder/{builder_id}/download",
        }

        # Simulate saving result to cache for retrieval later (as per original implementation pattern)
        # In reality, this would trigger the background task.
        # We keep the original pattern of just returning the metadata immediately.

        return response

    async def get_builder_report(self, builder_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key("builder_report", builder_id=str(builder_id))
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Builder report not found")
        return cached

    async def create_visualization(
        self, data: VisualizationCreate, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, data.report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        viz_id = uuid4()
        viz_data = self._generate_visualization_data(
            data.visualization.type, data.aggregation_method
        )

        response = {
            "id": str(viz_id),
            "report_id": str(data.report_id),
            "config": data.visualization.dict(),
            "data": viz_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await self._set_cached_result(
            self._get_cache_key("visualization", viz_id=str(viz_id)),
            response,
            REPORT_CACHE_TTL,
        )
        return response

    def _generate_visualization_data(
        self, viz_type: VisualizationType, aggregation: str
    ) -> Dict[str, Any]:
        if viz_type in [VisualizationType.LINE_CHART, VisualizationType.AREA_CHART]:
            return {
                "labels": ["Jan", "Feb", "Mar"],
                "datasets": [{"label": "Series 1", "data": [65, 59, 80]}],
            }
        elif viz_type == VisualizationType.BAR_CHART:
            return {"labels": ["A", "B", "C"], "data": [10, 20, 30]}
        elif viz_type == VisualizationType.PIE_CHART:
            return {"labels": ["Active", "Inactive"], "data": [80, 20]}
        elif viz_type == VisualizationType.GAUGE:
            return {"value": 75, "min": 0, "max": 100}
        elif viz_type == VisualizationType.HEATMAP:
            return {
                "rows": ["R1", "R2"],
                "columns": ["C1", "C2"],
                "data": [[1, 2], [3, 4]],
            }
        return {"data": []}

    async def get_visualization(self, visualization_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key("visualization", viz_id=str(visualization_id))
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Not found")
        return cached

    async def delete_visualization(self, visualization_id: UUID) -> None:
        await self._invalidate_cache_pattern(f"*visualization*{visualization_id}*")

    async def create_delivery_schedule(
        self, data: DeliveryConfigCreate, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, data.report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        schedule_id = uuid4()
        response = {
            "id": str(schedule_id),
            "report_id": str(data.report_id),
            "name": data.name,
            "description": data.description,
            "method": data.method.value,
            "schedule": data.schedule.dict(),
            "email_config": data.email_config.dict() if data.email_config else None,
            "webhook_config": data.webhook_config.dict()
            if data.webhook_config
            else None,
            "export_format": data.export_format.value,
            "is_active": data.is_active,
            "next_run": None,
            "last_run": None,
            "last_status": None,
            "run_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
        }

        await self._set_cached_result(
            self._get_cache_key("delivery_schedule", schedule_id=str(schedule_id)),
            response,
            SCHEDULED_CACHE_TTL,
        )
        return response

    async def get_delivery_schedule(self, schedule_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key(
            "delivery_schedule", schedule_id=str(schedule_id)
        )
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Not found")
        return cached

    async def delete_delivery_schedule(self, schedule_id: UUID) -> None:
        await self._invalidate_cache_pattern(f"*delivery_schedule*{schedule_id}*")

    async def share_report(
        self, data: ReportShareCreate, user_id: UUID, role: UserRole
    ) -> List[Dict[str, Any]]:
        if not self._check_report_access(role, user_id, data.report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        shares = []
        for shared_user_id in data.user_ids:
            expires_at = None
            if data.expires_at:
                expires_at = data.expires_at.replace(tzinfo=None).isoformat()
            share = {
                "id": str(uuid4()),
                "report_id": str(data.report_id),
                "shared_with": str(shared_user_id),
                "permission_level": data.permission_level.value,
                "shared_by": str(user_id),
                "shared_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at,
                "is_active": True,
            }
            shares.append(share)
        return shares

    async def create_public_link(
        self, data: PublicLinkCreate, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, data.report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        link_id = uuid4()
        token = hashlib.sha256(str(link_id).encode()).hexdigest()[:32]
        response = {
            "id": str(link_id),
            "report_id": str(data.report_id),
            "token": token,
            "url": f"/api/v2/enhanced-reports/public/{token}",
            "expires_at": data.expires_at.isoformat() if data.expires_at else None,
            "password_protected": data.password_protected,
            "max_views": data.max_views,
            "view_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
            "is_active": True,
        }
        await self._set_cached_result(
            self._get_cache_key("public_link", token=token), response, REPORT_CACHE_TTL
        )
        return response

    async def export_multi_format(
        self, data: MultiFormatExportRequest, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, data.report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        export_id = uuid4()
        response = {
            "export_id": str(export_id),
            "report_id": str(data.report_id),
            "formats": [f.value for f in data.formats],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return self._normalize_export_response(
            response, export_id=export_id, report_id=data.report_id
        )

    async def get_export_status(self, export_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key("export", export_id=str(export_id))
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Not found")
        return self._normalize_export_response(cached, export_id=export_id)

    async def get_report_history(
        self, report_id: UUID, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        # Mock history
        versions = [
            {
                "version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": str(user_id),
                "change_summary": "Initial",
                "configuration_snapshot": {},
                "data_hash": hashlib.sha256(
                    f"{report_id}:1".encode()
                ).hexdigest(),
            }
        ]
        return {
            "report_id": str(report_id),
            "current_version": 1,
            "versions": versions,
            "total_versions": 1,
        }

    async def restore_report_version(
        self, report_id: UUID, data: ReportRestoreRequest, user_id: UUID, role: UserRole
    ) -> Dict[str, Any]:
        if not self._check_report_access(role, user_id, report_id):
            raise HTTPException(status_code=403, detail="Access denied")

        return {
            "id": str(report_id),
            "name": f"Report restored to v{data.version}",
            "description": "Restored",
            "fields": [],
            "filters": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
            "row_count": 0,
            "generation_time_seconds": 0.0,
            "download_url": f"/api/v2/enhanced-reports/builder/{report_id}/download",
        }

    async def create_dashboard(
        self, data: DashboardCreate, user_id: UUID
    ) -> Dict[str, Any]:
        dashboard_id = uuid4()
        response = {
            "id": str(dashboard_id),
            "name": data.name,
            "description": data.description,
            "layout": data.layout.value,
            "widgets": [w.dict() for w in data.widgets],
            "auto_refresh": data.auto_refresh,
            "refresh_interval_seconds": data.refresh_interval_seconds,
            "is_public": data.is_public,
            "shared_with": data.shared_with,
            "theme": data.theme.value if hasattr(data.theme, "value") else data.theme,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        response = self._normalize_dashboard_response(response, user_id=user_id)
        await self._set_cached_result(
            self._get_cache_key("dashboard", dashboard_id=str(dashboard_id)),
            response,
            DASHBOARD_CACHE_TTL,
        )
        return response

    async def get_dashboard(self, dashboard_id: UUID) -> Dict[str, Any]:
        cache_key = self._get_cache_key("dashboard", dashboard_id=str(dashboard_id))
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return self._normalize_dashboard_response(cached)

    async def update_dashboard(
        self, dashboard_id: UUID, request: DashboardUpdate, user_id: UUID
    ) -> Dict[str, Any]:
        cache_key = self._get_cache_key("dashboard", dashboard_id=str(dashboard_id))
        cached = await self._get_cached_result(cache_key)
        if not cached:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        cached = self._normalize_dashboard_response(cached, user_id=user_id)
        if request.name:
            cached["name"] = request.name
        if request.description is not None:
            cached["description"] = request.description
        if request.widgets is not None:
            cached["widgets"] = [w.dict() for w in request.widgets]
        cached["updated_at"] = datetime.now(timezone.utc).isoformat()

        cached = self._normalize_dashboard_response(cached, user_id=user_id)
        await self._set_cached_result(cache_key, cached, DASHBOARD_CACHE_TTL)
        await self._invalidate_cache_pattern(f"*dashboard*{dashboard_id}*")
        return cached

    async def delete_dashboard(self, dashboard_id: UUID) -> None:
        await self._invalidate_cache_pattern(f"*dashboard*{dashboard_id}*")

    async def create_dashboard_snapshot(
        self, dashboard_id: UUID, data: DashboardSnapshotCreate, user_id: UUID
    ) -> Dict[str, Any]:
        snapshot_id = uuid4()
        response = {
            "id": str(snapshot_id),
            "dashboard_id": str(dashboard_id),
            "name": data.name,
            "description": data.description,
            "snapshot_data": {
                "widgets": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": str(user_id),
        }
        return response
