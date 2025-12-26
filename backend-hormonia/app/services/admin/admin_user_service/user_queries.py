"""
User query and statistics operations.

Handles user search, filtering, summaries, and statistics generation.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, func
from sqlalchemy.orm import joinedload

from app.models.user import User, UserRole
from .schemas import (
    UserSearchFilters,
    UserSummary,
    PaginatedUsersResponse,
    UserStatistics,
)

logger = logging.getLogger(__name__)


class UserQueriesMixin:
    """Mixin for user query and statistics operations."""

    async def get_user_summary(self, user_id: UUID) -> Optional[UserSummary]:
        """
        Get user summary with additional computed fields.

        Args:
            user_id: User ID

        Returns:
            User summary if found, None otherwise
        """
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        # Get patient count for doctors
        total_patients = 0
        if user.role == UserRole.DOCTOR:
            total_patients = len(user.patients) if user.patients else 0

        # TODO: Get last login and failed attempts from audit logs
        # For now, we'll use None/0 as placeholders
        last_login = None
        failed_login_attempts = 0

        return UserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            total_patients=total_patients,
            last_login=last_login,
            failed_login_attempts=failed_login_attempts,
        )

    async def search_users(
        self,
        filters: UserSearchFilters,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedUsersResponse:
        """
        Search users with enhanced filters and pagination.

        Args:
            filters: Search filters
            page: Page number (1-based)
            per_page: Items per page
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)

        Returns:
            Paginated users response
        """
        query = self.db.query(User)

        # Apply filters
        if filters.email:
            query = query.filter(User.email.ilike(f"%{filters.email}%"))
        if filters.full_name:
            query = query.filter(User.full_name.ilike(f"%{filters.full_name}%"))
        if filters.role is not None:
            query = query.filter(User.role == filters.role)
        if filters.is_active is not None:
            query = query.filter(User.is_active == filters.is_active)
        if filters.created_after:
            query = query.filter(User.created_at >= filters.created_after)
        if filters.created_before:
            query = query.filter(User.created_at <= filters.created_before)

        # TODO: Add filters for last_login_after, last_login_before, has_patients
        # These would require joins with audit logs or patient tables

        # Get total count
        total = query.count()

        # Apply sorting
        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        # Apply pagination with eager loading to prevent N+1 queries
        # FIX: Load patients relationship in single query instead of per-user queries
        offset = (page - 1) * per_page
        users = (
            query
            .options(joinedload(User.patients))  # Eager load patients for doctor summary
            .offset(offset)
            .limit(per_page)
            .all()
        )

        # Convert to user summaries directly from loaded users (no additional queries)
        user_summaries = []
        for user in users:
            # Build summary directly instead of calling get_user_summary(user.id)
            total_patients = 0
            if user.role == UserRole.DOCTOR:
                total_patients = len(user.patients) if user.patients else 0

            summary = UserSummary(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at,
                updated_at=user.updated_at,
                total_patients=total_patients,
                last_login=None,  # TODO: Get from audit logs
                failed_login_attempts=0,  # TODO: Get from audit logs
            )
            user_summaries.append(summary)

        total_pages = (total + per_page - 1) // per_page

        return PaginatedUsersResponse(
            users=user_summaries,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def get_user_statistics(self) -> UserStatistics:
        """
        Get enhanced user statistics for admin dashboard.

        Returns:
            User statistics

        FIX: Optimized from 7+ queries to 3 queries using GROUP BY
        """
        # Single query for total and active counts
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active).count()
        inactive_users = total_users - active_users

        # FIX: Single GROUP BY query instead of N queries per role
        # This reduces 5 queries to 1 query
        role_counts = (
            self.db.query(User.role, func.count(User.id))
            .group_by(User.role)
            .all()
        )

        # Build users_by_role dict from grouped results
        users_by_role = {role.value: 0 for role in UserRole}  # Initialize all roles to 0
        for role, count in role_counts:
            if role:
                users_by_role[role.value] = count

        # Recent registrations (last 30 days)
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_registrations = (
            self.db.query(User).filter(User.created_at >= thirty_days_ago).count()
        )

        # TODO: Get recent logins from audit logs
        # For now, we'll use 0 as placeholder
        recent_logins = 0

        return UserStatistics(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            users_by_role=users_by_role,
            recent_registrations=recent_registrations,
            recent_logins=recent_logins,
        )
