"""
Cursor pagination for patient listing with Redis caching.

This module provides efficient cursor-based pagination with
Redis caching for patient lists, preventing N+1 queries and
optimizing query performance.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.models.message import Message
from app.models.patient import FlowState, Patient

from .encryption_helpers import build_search_criteria

logger = logging.getLogger(__name__)


class PatientPaginationMixin:
    """
    Cursor-based pagination with Redis caching for performance.

    Provides efficient pagination with:
    - Cursor-based navigation
    - Redis caching for total counts (60s TTL)
    - Optimized eager loading
    - LGPD-compliant filtering

    Methods:
        list_v2: Advanced listing with cursor pagination and filtering.
        list_patients_optimized: Optimized listing with N+1 prevention.
    """

    def _get_cache_key(self, prefix: str, filters: Dict[str, Any]) -> str:
        """Generate deterministic cache key from filters"""
        # Sort filters for consistent hashing
        filter_str = json.dumps(filters, sort_keys=True, default=str)
        # Use SHA-256 instead of MD5 for better collision resistance
        filter_hash = hashlib.sha256(filter_str.encode()).hexdigest()[:16]
        return f"patient:{prefix}:{filter_hash}"

    def _get_cached_count(self, filters: Dict[str, Any]) -> Optional[int]:
        """Get cached total count if available"""
        if not self.redis:
            return None

        try:
            cache_key = self._get_cache_key("count", filters)
            cached = self.redis.get(cache_key)
            if cached:
                return int(cached)
        except Exception:
            pass  # Cache miss or error - continue without cache
        return None

    def _set_cached_count(self, filters: Dict[str, Any], count: int, ttl: int = 60):
        """Cache total count with TTL"""
        if not self.redis:
            return

        try:
            cache_key = self._get_cache_key("count", filters)
            self.redis.setex(cache_key, ttl, str(count))
        except Exception:
            pass  # Cache write failure - continue without cache

    def list_v2(
        self,
        filters: Dict[str, Any],
        cursor_data: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        eager_load: List[str] = None,
    ) -> Tuple[List[Patient], bool, Optional[str], Optional[int]]:
        """
        Advanced list method with cursor pagination, filtering and eager loading.

        PERFORMANCE OPTIMIZATIONS:
        - joinedload for 1:1 relationships (doctor)
        - selectinload for 1:many relationships (messages, quiz_sessions, flow_states)
        - Cached total count (Redis 60s TTL)
        - Batch loading strategy for nested relationships

        Returns:
            (patients, has_more, next_cursor_str, total_count)
        """
        query = self.db.query(Patient)

        # 1. OPTIMIZED EAGER LOADING
        query = self._apply_eager_loading(query, eager_load)

        # 2. Build Filter Criteria
        criteria = []

        # Always filter soft-deleted
        criteria.append(Patient.deleted_at.is_(None))

        # Doctor Filter
        if filters.get("doctor_id"):
            criteria.append(Patient.doctor_id == filters["doctor_id"])

        # Search (Name, Email hash, or Phone hash) - LGPD compliant
        if filters.get("search"):
            search_criteria = build_search_criteria(filters["search"])
            if search_criteria:
                criteria.append(or_(*search_criteria))

        # Status Filter
        if filters.get("status"):
            status_val = filters["status"]
            # Handle aliases if passed, though Controller should ideally handle this
            if isinstance(status_val, str):
                try:
                    status_val = FlowState(status_val)
                except ValueError:
                    pass  # Let it fail or be ignored if invalid
            criteria.append(Patient.flow_state == status_val)

        if filters.get("has_active_flow") is not None:
            if filters["has_active_flow"]:
                criteria.append(Patient.flow_state == FlowState.ACTIVE)
            else:
                criteria.append(
                    Patient.flow_state.in_(
                        [FlowState.PAUSED, FlowState.CANCELLED, FlowState.COMPLETED]
                    )
                )

        # Treatment Filters
        if filters.get("treatment_type"):
            criteria.append(
                Patient.treatment_type.ilike(f"%{filters['treatment_type']}%")
            )
        if filters.get("treatment_phase"):
            criteria.append(Patient.treatment_phase == filters["treatment_phase"])
        if filters.get("start_date_from"):
            criteria.append(Patient.treatment_start_date >= filters["start_date_from"])
        if filters.get("start_date_to"):
            criteria.append(Patient.treatment_start_date <= filters["start_date_to"])

        # Date Filters
        if filters.get("created_after"):
            criteria.append(Patient.created_at >= filters["created_after"])
        if filters.get("created_before"):
            criteria.append(Patient.created_at <= filters["created_before"])

        # 3. Cursor Pagination Logic
        if cursor_data and "id" in cursor_data:
            cursor_id = (
                UUID(cursor_data["id"])
                if isinstance(cursor_data["id"], str)
                else cursor_data["id"]
            )
            cursor_val = cursor_data.get(sort_by)

            # Convert isoformat string back to datetime if needed
            if isinstance(cursor_val, str) and sort_by in [
                "created_at",
                "updated_at",
                "treatment_start_date",
            ]:
                try:
                    cursor_val = datetime.fromisoformat(
                        cursor_val.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass  # Handle date vs datetime if needed

            sort_col = getattr(Patient, sort_by)

            if sort_order == "desc":
                # records where (col < cursor) OR (col == cursor AND id > cursor_id)
                criteria.append(
                    or_(
                        sort_col < cursor_val,
                        and_(sort_col == cursor_val, Patient.id > cursor_id),
                    )
                )
            else:
                # records where (col > cursor) OR (col == cursor AND id > cursor_id)
                criteria.append(
                    or_(
                        sort_col > cursor_val,
                        and_(sort_col == cursor_val, Patient.id > cursor_id),
                    )
                )

        # Apply Filters
        if criteria:
            query = query.filter(and_(*criteria))

        # 4. OPTIMIZED TOTAL COUNT (Only on first page)
        total = None
        if not cursor_data:
            total = self._get_cached_count(filters)

            if total is None:
                # Build clean filter criteria for count (exclude cursor pagination)
                count_criteria = self._build_count_criteria(filters)

                # Execute optimized count query
                count_q = self.db.query(func.count(Patient.id))
                if count_criteria:
                    count_q = count_q.filter(and_(*count_criteria))

                total = count_q.scalar()

                # Cache the count for 60 seconds
                self._set_cached_count(filters, total, ttl=60)

        # 5. Sorting
        sort_col = getattr(Patient, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_col.desc(), Patient.id)
        else:
            query = query.order_by(sort_col.asc(), Patient.id)

        # 6. Limit
        results = query.limit(limit + 1).all()

        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        # 7. Next Cursor
        next_cursor = None
        if has_more and results:
            last_item = results[-1]
            last_val = getattr(last_item, sort_by)
            if isinstance(last_val, (datetime, date)):
                last_val = last_val.isoformat()

            next_cursor_data = {"id": str(last_item.id), sort_by: last_val}
            next_cursor = base64.b64encode(
                json.dumps(next_cursor_data).encode()
            ).decode()

        return results, has_more, next_cursor, total

    def _build_count_criteria(self, filters: Dict[str, Any]) -> List:
        """Build filter criteria for count queries (excludes cursor pagination)"""
        count_criteria = []
        count_criteria.append(Patient.deleted_at.is_(None))

        if filters.get("doctor_id"):
            count_criteria.append(Patient.doctor_id == filters["doctor_id"])

        if filters.get("search"):
            search_criteria = build_search_criteria(filters["search"])
            if search_criteria:
                count_criteria.append(or_(*search_criteria))

        if filters.get("status"):
            status_val = filters["status"]
            if isinstance(status_val, str):
                try:
                    status_val = FlowState(status_val)
                except ValueError as e:
                    logger.warning(f"Invalid FlowState value: {status_val}, error: {e}")
            count_criteria.append(Patient.flow_state == status_val)

        if filters.get("has_active_flow") is not None:
            if filters["has_active_flow"]:
                count_criteria.append(Patient.flow_state == FlowState.ACTIVE)
            else:
                count_criteria.append(
                    Patient.flow_state.in_(
                        [FlowState.PAUSED, FlowState.CANCELLED, FlowState.COMPLETED]
                    )
                )

        if filters.get("treatment_type"):
            count_criteria.append(
                Patient.treatment_type.ilike(f"%{filters['treatment_type']}%")
            )

        if filters.get("treatment_phase"):
            count_criteria.append(Patient.treatment_phase == filters["treatment_phase"])

        if filters.get("start_date_from"):
            count_criteria.append(
                Patient.treatment_start_date >= filters["start_date_from"]
            )

        if filters.get("start_date_to"):
            count_criteria.append(
                Patient.treatment_start_date <= filters["start_date_to"]
            )

        if filters.get("created_after"):
            count_criteria.append(Patient.created_at >= filters["created_after"])

        if filters.get("created_before"):
            count_criteria.append(Patient.created_at <= filters["created_before"])

        return count_criteria

    async def list_patients_optimized(
        self,
        doctor_id: str,
        filters: Optional[Dict[str, Any]] = None,
        cursor_data: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Patient], bool, Optional[str], Optional[int]]:
        """
        OPTIMIZED patient listing with comprehensive N+1 prevention.

        PERFORMANCE FEATURES:
        1. Single query with all necessary joins
        2. Redis-cached total count (60s TTL)
        3. Cursor-based pagination
        4. Batch loading for all relationships
        5. No N+1 queries - guaranteed

        QUERY OPTIMIZATION:
        - joinedload: doctor (1:1)
        - selectinload: messages, quiz_sessions, flow_states (1:many)
        - Nested joinedload: Message.sender (1:1 within 1:many)

        EXPECTED QUERIES:
        - Page 1: 4 queries (main + 3 selectinload batches)
        - Page N: 4 queries (same)
        - With cache: 3 queries (skip count)

        Args:
            doctor_id: Doctor UUID
            filters: Additional filters
            cursor_data: Cursor for pagination
            limit: Results per page
            sort_by: Sort column
            sort_order: 'asc' or 'desc'

        Returns:
            (patients, has_more, next_cursor, total_count)
        """
        filters = filters or {}
        filters["doctor_id"] = doctor_id

        # Build query with optimal eager loading
        query = self.db.query(Patient)

        # EAGER LOADING STRATEGY:
        # 1. joinedload for 1:1 relationships (single query via JOIN)
        query = query.options(joinedload(Patient.doctor))

        # 2. selectinload for 1:many relationships (separate optimized queries)
        query = query.options(
            # Messages with sender (nested join)
            selectinload(Patient.messages).joinedload(Message.sender),
            # Quiz sessions
            selectinload(Patient.quiz_sessions),
            # Flow states
            selectinload(Patient.flow_states),
            # Treatments
            selectinload(Patient.treatments),
            # Appointments
            selectinload(Patient.appointments),
            # Medications
            selectinload(Patient.medications),
        )

        # Build filter criteria
        criteria = [Patient.deleted_at.is_(None)]
        criteria.append(Patient.doctor_id == doctor_id)

        # Search filter - LGPD compliant with hash lookups
        if filters.get("search"):
            search_criteria = build_search_criteria(filters["search"])
            if search_criteria:
                criteria.append(or_(*search_criteria))

        # Status filter
        if filters.get("status"):
            status_val = filters["status"]
            if isinstance(status_val, str):
                try:
                    status_val = FlowState(status_val)
                except ValueError as e:
                    logger.warning(f"Invalid FlowState value: {status_val}, error: {e}")
            criteria.append(Patient.flow_state == status_val)

        # Treatment filters
        if filters.get("treatment_type"):
            criteria.append(
                Patient.treatment_type.ilike(f"%{filters['treatment_type']}%")
            )

        if filters.get("treatment_phase"):
            criteria.append(Patient.treatment_phase == filters["treatment_phase"])

        # Date filters
        if filters.get("created_after"):
            criteria.append(Patient.created_at >= filters["created_after"])

        if filters.get("created_before"):
            criteria.append(Patient.created_at <= filters["created_before"])

        # Cursor pagination
        if cursor_data and "id" in cursor_data:
            cursor_id = (
                UUID(cursor_data["id"])
                if isinstance(cursor_data["id"], str)
                else cursor_data["id"]
            )
            cursor_val = cursor_data.get(sort_by)

            if isinstance(cursor_val, str) and sort_by in ["created_at", "updated_at"]:
                try:
                    cursor_val = datetime.fromisoformat(
                        cursor_val.replace("Z", "+00:00")
                    )
                except ValueError as e:
                    logger.warning(
                        f"Failed to parse cursor datetime: {cursor_val}, error: {e}"
                    )

            sort_col = getattr(Patient, sort_by)

            if sort_order == "desc":
                criteria.append(
                    or_(
                        sort_col < cursor_val,
                        and_(sort_col == cursor_val, Patient.id > cursor_id),
                    )
                )
            else:
                criteria.append(
                    or_(
                        sort_col > cursor_val,
                        and_(sort_col == cursor_val, Patient.id > cursor_id),
                    )
                )

        # Apply filters
        query = query.filter(and_(*criteria))

        # Cached total count (first page only)
        total = None
        if not cursor_data:
            total = self._get_cached_count(filters)
            if total is None:
                count_q = self.db.query(func.count(Patient.id)).filter(and_(*criteria))
                total = count_q.scalar()
                self._set_cached_count(filters, total, ttl=60)

        # Sorting
        sort_col = getattr(Patient, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_col.desc(), Patient.id)
        else:
            query = query.order_by(sort_col.asc(), Patient.id)

        # Execute with limit + 1 for has_more check
        results = query.limit(limit + 1).all()

        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and results:
            last_item = results[-1]
            last_val = getattr(last_item, sort_by)
            if isinstance(last_val, (datetime, date)):
                last_val = last_val.isoformat()

            next_cursor_data = {"id": str(last_item.id), sort_by: last_val}
            next_cursor = base64.b64encode(
                json.dumps(next_cursor_data).encode()
            ).decode()

        return results, has_more, next_cursor, total
