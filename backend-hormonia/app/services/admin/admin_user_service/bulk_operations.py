"""
Bulk operations for user administration.

Handles bulk activation, deactivation, and deletion of users.
"""

import logging
from typing import Optional
from sqlalchemy import and_
from fastapi import HTTPException, status

from app.models.user import User, UserRole
from .schemas import BulkUserOperationRequest, BulkUserOperationResult

logger = logging.getLogger(__name__)


class BulkOperationsMixin:
    """Mixin for bulk user operations."""

    async def bulk_user_operation(
        self,
        bulk_request: BulkUserOperationRequest,
        admin_user: User,
        request_info: Optional[dict] = None,
    ) -> BulkUserOperationResult:
        """
        Perform bulk operations on multiple users.

        Args:
            bulk_request: Bulk operation request
            admin_user: Admin user performing the operation
            request_info: Request information for audit

        Returns:
            Bulk operation result
        """
        # Check admin permissions
        self._check_admin_permissions(admin_user, f"bulk_{bulk_request.operation}")

        successful = []
        failed = []

        # FIX: Bulk fetch all users in single query instead of N queries
        # This prevents N+1 query problem (was: 1 query per user)
        users_query = self.db.query(User).filter(User.id.in_(bulk_request.user_ids))
        users = users_query.all()
        user_map = {user.id: user for user in users}

        # Pre-calculate admin count once instead of per-user checks
        active_admin_count = (
            self.db.query(User)
            .filter(
                and_(
                    User.role == UserRole.ADMIN,
                    User.is_active
                )
            )
            .count()
        )

        for user_id in bulk_request.user_ids:
            try:
                user = user_map.get(user_id)
                if not user:
                    failed.append({"user_id": str(user_id), "reason": "User not found"})
                    continue

                # Perform the operation
                if bulk_request.operation == "activate":
                    if user.is_active:
                        failed.append(
                            {
                                "user_id": str(user_id),
                                "reason": "User is already active",
                            }
                        )
                        continue
                    user.is_active = True

                elif bulk_request.operation == "deactivate":
                    if user.role == UserRole.ADMIN:
                        # Use pre-calculated admin count instead of querying per user
                        # Adjust for current user being deactivated
                        remaining_admins = active_admin_count - 1 if user.is_active else active_admin_count
                        if remaining_admins == 0:
                            failed.append(
                                {
                                    "user_id": str(user_id),
                                    "reason": "Cannot deactivate the last active admin user",
                                }
                            )
                            continue

                    if not user.is_active:
                        failed.append(
                            {
                                "user_id": str(user_id),
                                "reason": "User is already inactive",
                            }
                        )
                        continue
                    user.is_active = False

                elif bulk_request.operation == "delete":
                    # Prevent deleting the last admin
                    if user.role == UserRole.ADMIN:
                        # Use pre-calculated admin count instead of querying per user
                        remaining_admins = active_admin_count - 1 if user.is_active else active_admin_count
                        if remaining_admins == 0:
                            failed.append(
                                {
                                    "user_id": str(user_id),
                                    "reason": "Cannot delete the last active admin user",
                                }
                            )
                            continue

                    # Soft delete
                    user.is_active = False

                successful.append(user_id)

            except Exception as e:
                failed.append({"user_id": str(user_id), "reason": f"Error: {str(e)}"})

        try:
            self.db.commit()

            # Log bulk operation
            await self.log_admin_action(
                action_type=f"bulk_{bulk_request.operation}",
                admin_user=admin_user,
                action_data={
                    "operation": bulk_request.operation,
                    "total_requested": len(bulk_request.user_ids),
                    "successful_count": len(successful),
                    "failed_count": len(failed),
                    "reason": bulk_request.reason,
                    "successful_ids": [str(uid) for uid in successful],
                    "failed_details": failed,
                },
            )

            summary = f"Bulk {bulk_request.operation}: {len(successful)} successful, {len(failed)} failed"
            logger.info(f"{summary} by admin {admin_user.email}")

            return BulkUserOperationResult(
                operation=bulk_request.operation,
                total_requested=len(bulk_request.user_ids),
                successful=successful,
                failed=failed,
                summary=summary,
            )

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type=f"bulk_{bulk_request.operation}_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "operation": bulk_request.operation,
                },
                result="failure",
            )
            logger.error(f"Failed bulk {bulk_request.operation}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to perform bulk {bulk_request.operation}",
            )
