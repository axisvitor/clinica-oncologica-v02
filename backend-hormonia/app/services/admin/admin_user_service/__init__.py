"""
Admin User Service Package.

Modular package structure for user administration with full backward compatibility.
"""

import logging
from typing import Any

from app.models.user import User, UserRole
from app.middleware.admin_permissions import AdminAuditMixin
from app.exceptions import AuthorizationError

# Import all schemas for re-export
from .schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    UserPasswordUpdateRequest,
    UserSearchFilters,
    UserSummary,
    PaginatedUsersResponse,
    UserStatistics,
    PasswordResetRequest,
    PasswordResetResult,
    BulkUserOperationRequest,
    BulkUserOperationResult,
    EmailValidationRequest,
    EmailValidationResult,
)

# Import validators
from .validators import (
    validate_email_format,
    validate_full_name,
    validate_password,
    validate_email_advanced,
    generate_temporary_password,
)

# Import mixins
from .user_crud import UserCRUDMixin
from .password_management import PasswordManagementMixin
from .bulk_operations import BulkOperationsMixin
from .user_queries import UserQueriesMixin

logger = logging.getLogger(__name__)


class AdminUserService(
    AdminAuditMixin,
    UserCRUDMixin,
    PasswordManagementMixin,
    BulkOperationsMixin,
    UserQueriesMixin,
):
    """
    Service for user administration operations with enhanced security and audit logging.

    This service combines multiple mixins to provide comprehensive user management:
    - UserCRUDMixin: Basic CRUD operations
    - PasswordManagementMixin: Password reset and updates
    - BulkOperationsMixin: Bulk user operations
    - UserQueriesMixin: Search and statistics
    """

    def __init__(self, db: Any):
        super().__init__(db)
        self.logger = logging.getLogger(__name__)

    def _check_admin_permissions(self, admin_user: User, operation: str) -> None:
        """Check if admin user has permissions for the operation."""
        if not admin_user:
            raise AuthorizationError("Admin user required")

        if admin_user.role != UserRole.ADMIN:
            raise AuthorizationError(f"Admin role required for {operation}")

        if not admin_user.is_active:
            raise AuthorizationError("Admin user account is not active")


# Re-export everything for backward compatibility
__all__ = [
    # Main service class
    "AdminUserService",
    # Schemas
    "UserCreateRequest",
    "UserUpdateRequest",
    "UserPasswordUpdateRequest",
    "UserSearchFilters",
    "UserSummary",
    "PaginatedUsersResponse",
    "UserStatistics",
    "PasswordResetRequest",
    "PasswordResetResult",
    "BulkUserOperationRequest",
    "BulkUserOperationResult",
    "EmailValidationRequest",
    "EmailValidationResult",
    # Validators
    "validate_email_format",
    "validate_full_name",
    "validate_password",
    "validate_email_advanced",
    "generate_temporary_password",
    # Mixins (for advanced usage)
    "UserCRUDMixin",
    "PasswordManagementMixin",
    "BulkOperationsMixin",
    "UserQueriesMixin",
]
