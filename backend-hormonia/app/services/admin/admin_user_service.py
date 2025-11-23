"""
Enhanced User Administration Service.

Provides comprehensive user management functionality including:
- User CRUD operations with email validation
- Password hashing using passlib/bcrypt
- Role management and permission checks
- User activation/deactivation
- Password reset with temporary passwords
- Batch operations
- User search and filtering with advanced options
- Comprehensive audit logging
"""
import logging
import secrets
import string
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple, Union
from uuid import UUID
# from sqlalchemy.orm import
from sqlalchemy import and_, or_, func, desc, text
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr, Field, validator

from app.models.user import User, UserRole
from app.services.audit_service import AuditService
from app.utils.security import get_password_hash, verify_password, validate_password_strength
from app.middleware.admin_permissions import AdminAuditMixin
from app.exceptions import (
    AuthorizationError, ValidationError, NotFoundError,
    ConflictError, DatabaseError
)

logger = logging.getLogger(__name__)


# Enhanced Pydantic models for user administration
class UserCreateRequest(BaseModel):
    """Request model for creating a new user with enhanced validation."""
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be 8-128 characters with mixed case, numbers, and symbols"
    )
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: UserRole = UserRole.DOCTOR
    is_active: bool = True

    @validator('email')
    def validate_email_format(cls, v):
        """Enhanced email validation."""
        try:
            # Basic regex validation for email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError("Invalid email format")

            # Normalize email (lowercase domain)
            local, domain = v.split('@')
            normalized_email = f"{local}@{domain.lower()}"
            return normalized_email
        except Exception as e:
            raise ValueError(f"Invalid email format: {str(e)}")

    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength."""
        validation_result = validate_password_strength(v)
        if not validation_result['is_valid']:
            raise ValueError(f"Password validation failed: {'; '.join(validation_result['issues'])}")
        return v

    @validator('full_name')
    def validate_full_name(cls, v):
        """Validate full name format."""
        if v is not None:
            # Remove extra whitespace
            v = ' '.join(v.split())
            # Check for valid characters (letters, spaces, hyphens, apostrophes, accented characters)
            if not re.match(r"^[a-zA-Z\s\-\'\u00C0-\u017F]+$", v):
                raise ValueError("Full name can only contain letters, spaces, hyphens, and apostrophes")
        return v

    class Config:
        use_enum_values = True


class UserUpdateRequest(BaseModel):
    """Request model for updating a user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

    @validator('email')
    def validate_email_format(cls, v):
        """Enhanced email validation."""
        if v is not None:
            try:
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, v):
                    raise ValueError("Invalid email format")
                local, domain = v.split('@')
                return f"{local}@{domain.lower()}"
            except Exception as e:
                raise ValueError(f"Invalid email format: {str(e)}")
        return v

    @validator('full_name')
    def validate_full_name(cls, v):
        """Validate full name format."""
        if v is not None:
            v = ' '.join(v.split())
            if not re.match(r"^[a-zA-Z\s\-\'\u00C0-\u017F]+$", v):
                raise ValueError("Full name can only contain letters, spaces, hyphens, and apostrophes")
        return v

    class Config:
        use_enum_values = True


class UserPasswordUpdateRequest(BaseModel):
    """Request model for updating user password with validation."""
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password must be 8-128 characters with mixed case, numbers, and symbols"
    )
    confirm_password: str

    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password strength."""
        validation_result = validate_password_strength(v)
        if not validation_result['is_valid']:
            raise ValueError(f"Password validation failed: {'; '.join(validation_result['issues'])}")
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Ensure passwords match."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserSearchFilters(BaseModel):
    """Search filters for user queries with enhanced options."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    last_login_after: Optional[datetime] = None
    last_login_before: Optional[datetime] = None
    has_patients: Optional[bool] = None

    class Config:
        use_enum_values = True


class UserSummary(BaseModel):
    """Summary model for user data."""
    id: UUID
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Add computed fields
    total_patients: int = 0
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0

    class Config:
        from_attributes = True
        use_enum_values = True


class PaginatedUsersResponse(BaseModel):
    """Paginated response for user listings."""
    users: List[UserSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserStatistics(BaseModel):
    """User statistics for dashboard."""
    total_users: int
    active_users: int
    inactive_users: int
    users_by_role: Dict[str, int]
    recent_registrations: int
    recent_logins: int


class PasswordResetRequest(BaseModel):
    """Request model for password reset."""
    user_id: UUID
    send_email: bool = True
    temporary_password_length: int = Field(default=12, ge=8, le=32)


class PasswordResetResult(BaseModel):
    """Result of password reset operation."""
    user_id: UUID
    temporary_password: Optional[str] = None
    reset_token: Optional[str] = None
    expires_at: datetime
    email_sent: bool = False


class BulkUserOperationRequest(BaseModel):
    """Request model for bulk user operations."""
    user_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., pattern="^(activate|deactivate|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


class BulkUserOperationResult(BaseModel):
    """Result of bulk user operation."""
    operation: str
    total_requested: int
    successful: List[UUID]
    failed: List[Dict[str, Any]]
    summary: str


class EmailValidationRequest(BaseModel):
    """Request model for email validation."""
    email: EmailStr
    check_mx: bool = True
    check_deliverability: bool = False


class EmailValidationResult(BaseModel):
    """Result of email validation."""
    email: str
    is_valid: bool
    normalized_email: str
    issues: List[str]
    suggestions: List[str]


class AdminUserService(AdminAuditMixin):
    """Service for user administration operations with enhanced security and audit logging."""

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

    async def validate_email_advanced(self, email_request: EmailValidationRequest) -> EmailValidationResult:
        """Perform advanced email validation with domain checking."""
        issues = []
        suggestions = []

        try:
            # Basic format validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email_request.email):
                issues.append("Invalid email format")

            # Normalize email
            local, domain = email_request.email.split('@')
            normalized_email = f"{local}@{domain.lower()}"

            # Check for common typos in popular domains
            domain_suggestions = {
                'gmail.com': ['gmai.com', 'gmial.com', 'gmail.co'],
                'yahoo.com': ['yaho.com', 'yahoo.co'],
                'hotmail.com': ['hotmai.com', 'hotmal.com'],
                'outlook.com': ['outloo.com', 'outlook.co']
            }

            for correct_domain, typos in domain_suggestions.items():
                if domain in typos:
                    suggestions.append(f"Did you mean {local}@{correct_domain}?")

            # Check for disposable email domains (basic list)
            disposable_domains = {
                '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
                'mailinator.com', 'throwaway.email', 'temp-mail.org'
            }
            if domain in disposable_domains:
                issues.append("Disposable email addresses are not allowed")

            # Check email length limits
            if len(local) > 64:
                issues.append("Local part of email is too long (max 64 characters)")
            if len(domain) > 253:
                issues.append("Domain part of email is too long (max 253 characters)")

            is_valid = len(issues) == 0

            return EmailValidationResult(
                email=email_request.email,
                is_valid=is_valid,
                normalized_email=normalized_email,
                issues=issues,
                suggestions=suggestions
            )

        except Exception as e:
            self.logger.error(f"Email validation error: {e}")
            return EmailValidationResult(
                email=email_request.email,
                is_valid=False,
                normalized_email=email_request.email,
                issues=[f"Validation error: {str(e)}"],
                suggestions=[]
            )

    def _generate_temporary_password(self, length: int = 12) -> str:
        """Generate a secure temporary password."""
        # Use a mix of uppercase, lowercase, numbers, and symbols
        characters = string.ascii_letters + string.digits + "!@#$%^&*"

        # Ensure at least one character from each category
        password = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*")
        ]

        # Fill the rest randomly
        for _ in range(length - 4):
            password.append(secrets.choice(characters))

        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        return ''.join(password)

    async def create_user(
        self,
        user_data: UserCreateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """
        Create a new user with enhanced validation and audit logging.

        Args:
            user_data: User creation data
            admin_user: Admin user creating the user
            request_info: Request information for audit

        Returns:
            Created user

        Raises:
            HTTPException: If email already exists or validation fails
        """
        # Check admin permissions
        self._check_admin_permissions(admin_user, "create_user")

        # Validate email format and check for issues
        email_validation = await self.validate_email_advanced(
            EmailValidationRequest(email=user_data.email)
        )
        if not email_validation.is_valid:
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "invalid_email",
                    "email": user_data.email,
                    "email_issues": email_validation.issues
                },
                result="failure"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid email: {'; '.join(email_validation.issues)}"
            )

        # Check if email already exists
        existing_user = self.db.query(User).filter(
            User.email == email_validation.normalized_email
        ).first()
        if existing_user:
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "email_already_exists",
                    "email": email_validation.normalized_email
                },
                result="failure"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User with email {email_validation.normalized_email} already exists"
            )

        # Hash password
        hashed_password = get_password_hash(user_data.password)

        # Create user with normalized email
        new_user = User(
            email=email_validation.normalized_email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active
        )

        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)

            # Log successful creation
            await self.log_admin_action(
                action_type="user_created",
                admin_user=admin_user,
                target_user_id=new_user.id,
                action_data={
                    "user_email": new_user.email,
                    "user_role": new_user.role.value,
                    "is_active": new_user.is_active,
                    "email_normalized": email_validation.normalized_email != user_data.email
                }
            )

            self.logger.info(f"User created successfully: {new_user.email} by admin {admin_user.email}")
            return new_user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_creation_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "email": email_validation.normalized_email
                },
                result="failure"
            )
            self.logger.error(f"Failed to create user {email_validation.normalized_email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

    async def reset_user_password(
        self,
        reset_request: PasswordResetRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> PasswordResetResult:
        """
        Reset user password with temporary password generation.

        Args:
            reset_request: Password reset request data
            admin_user: Admin user performing the reset
            request_info: Request information for audit

        Returns:
            Password reset result

        Raises:
            HTTPException: If user not found or reset fails
        """
        # Check admin permissions
        self._check_admin_permissions(admin_user, "reset_password")

        user = await self.get_user_by_id(reset_request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {reset_request.user_id} not found"
            )

        try:
            # Generate temporary password
            temp_password = self._generate_temporary_password(reset_request.temporary_password_length)
            hashed_password = get_password_hash(temp_password)

            # Update user password
            user.hashed_password = hashed_password

            # Set expiration for temporary password (24 hours)
            expires_at = datetime.utcnow() + timedelta(hours=24)

            self.db.commit()

            # Log password reset (without storing the actual password)
            await self.log_admin_action(
                action_type="user_password_reset",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "temp_password_length": len(temp_password),
                    "expires_at": expires_at.isoformat(),
                    "email_notification_requested": reset_request.send_email
                }
            )

            # TODO: Implement email sending
            email_sent = False
            if reset_request.send_email:
                # This would integrate with email service
                # For now, we'll just log the intention
                self.logger.info(f"Email notification requested for password reset: {user.email}")

            self.logger.info(f"Password reset for user {user.email} by admin {admin_user.email}")

            return PasswordResetResult(
                user_id=user.id,
                temporary_password=temp_password,
                expires_at=expires_at,
                email_sent=email_sent
            )

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_password_reset_failed",
                admin_user=admin_user,
                target_user_id=reset_request.user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to reset password for user {reset_request.user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reset password"
            )

    async def bulk_user_operation(
        self,
        bulk_request: BulkUserOperationRequest,
        admin_user: User,
        request_info: Optional[dict] = None
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

        for user_id in bulk_request.user_ids:
            try:
                user = await self.get_user_by_id(user_id)
                if not user:
                    failed.append({
                        "user_id": str(user_id),
                        "reason": "User not found"
                    })
                    continue

                # Perform the operation
                if bulk_request.operation == "activate":
                    if user.is_active:
                        failed.append({
                            "user_id": str(user_id),
                            "reason": "User is already active"
                        })
                        continue
                    user.is_active = True

                elif bulk_request.operation == "deactivate":
                    if user.role == UserRole.ADMIN:
                        admin_count = self.db.query(User).filter(
                            and_(User.role == UserRole.ADMIN, User.is_active == True, User.id != user_id)
                        ).count()
                        if admin_count == 0:
                            failed.append({
                                "user_id": str(user_id),
                                "reason": "Cannot deactivate the last active admin user"
                            })
                            continue

                    if not user.is_active:
                        failed.append({
                            "user_id": str(user_id),
                            "reason": "User is already inactive"
                        })
                        continue
                    user.is_active = False

                elif bulk_request.operation == "delete":
                    # Prevent deleting the last admin
                    if user.role == UserRole.ADMIN:
                        admin_count = self.db.query(User).filter(
                            and_(User.role == UserRole.ADMIN, User.is_active == True, User.id != user_id)
                        ).count()
                        if admin_count == 0:
                            failed.append({
                                "user_id": str(user_id),
                                "reason": "Cannot delete the last active admin user"
                            })
                            continue

                    # Soft delete
                    user.is_active = False

                successful.append(user_id)

            except Exception as e:
                failed.append({
                    "user_id": str(user_id),
                    "reason": f"Error: {str(e)}"
                })

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
                    "failed_details": failed
                }
            )

            summary = f"Bulk {bulk_request.operation}: {len(successful)} successful, {len(failed)} failed"
            self.logger.info(f"{summary} by admin {admin_user.email}")

            return BulkUserOperationResult(
                operation=bulk_request.operation,
                total_requested=len(bulk_request.user_ids),
                successful=successful,
                failed=failed,
                summary=summary
            )

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type=f"bulk_{bulk_request.operation}_failed",
                admin_user=admin_user,
                action_data={
                    "reason": "database_error",
                    "error": str(e),
                    "operation": bulk_request.operation
                },
                result="failure"
            )
            self.logger.error(f"Failed bulk {bulk_request.operation}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to perform bulk {bulk_request.operation}"
            )

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        return self.db.query(User).filter(User.id == user_id).first()

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
            failed_login_attempts=failed_login_attempts
        )

    async def search_users(
        self,
        filters: UserSearchFilters,
        page: int = 1,
        per_page: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
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

        # Apply pagination
        offset = (page - 1) * per_page
        users = query.offset(offset).limit(per_page).all()

        # Convert to user summaries
        user_summaries = []
        for user in users:
            summary = await self.get_user_summary(user.id)
            if summary:
                user_summaries.append(summary)

        total_pages = (total + per_page - 1) // per_page

        return PaginatedUsersResponse(
            users=user_summaries,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )

    async def get_user_statistics(self) -> UserStatistics:
        """
        Get enhanced user statistics for admin dashboard.

        Returns:
            User statistics
        """
        # Basic counts
        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.is_active == True).count()
        inactive_users = total_users - active_users

        # Users by role
        users_by_role = {}
        for role in UserRole:
            count = self.db.query(User).filter(User.role == role).count()
            users_by_role[role.value] = count

        # Recent registrations (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_registrations = self.db.query(User).filter(
            User.created_at >= thirty_days_ago
        ).count()

        # TODO: Get recent logins from audit logs
        # For now, we'll use 0 as placeholder
        recent_logins = 0

        return UserStatistics(
            total_users=total_users,
            active_users=active_users,
            inactive_users=inactive_users,
            users_by_role=users_by_role,
            recent_registrations=recent_registrations,
            recent_logins=recent_logins
        )

    # Include all the existing methods from the original service
    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """Update user information with enhanced validation."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "update_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Check if new email already exists (if email is being updated)
        if user_data.email and user_data.email != user.email:
            # Validate the new email
            email_validation = await self.validate_email_advanced(
                EmailValidationRequest(email=user_data.email)
            )
            if not email_validation.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid email: {'; '.join(email_validation.issues)}"
                )

            existing_user = self.db.query(User).filter(
                and_(User.email == email_validation.normalized_email, User.id != user_id)
            ).first()
            if existing_user:
                await self.log_admin_action(
                    action_type="user_update_failed",
                    admin_user=admin_user,
                    target_user_id=user_id,
                    action_data={
                        "reason": "email_already_exists",
                        "new_email": email_validation.normalized_email
                    },
                    result="failure"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email {email_validation.normalized_email} is already in use"
                )

        # Store original values for audit
        original_values = {
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active
        }

        # Update fields
        if user_data.email is not None:
            email_validation = await self.validate_email_advanced(
                EmailValidationRequest(email=user_data.email)
            )
            user.email = email_validation.normalized_email
        if user_data.full_name is not None:
            user.full_name = user_data.full_name
        if user_data.role is not None:
            user.role = user_data.role
        if user_data.is_active is not None:
            user.is_active = user_data.is_active

        try:
            self.db.commit()
            self.db.refresh(user)

            # Log successful update
            await self.log_admin_action(
                action_type="user_updated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "original_values": original_values,
                    "new_values": {
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role.value,
                        "is_active": user.is_active
                    }
                }
            )

            self.logger.info(f"User {user.email} updated successfully by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_update_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to update user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )

    async def update_user_password(
        self,
        user_id: UUID,
        password_data: UserPasswordUpdateRequest,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> bool:
        """Update user password with enhanced validation."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "update_password")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Hash new password
        hashed_password = get_password_hash(password_data.new_password)

        try:
            user.hashed_password = hashed_password
            self.db.commit()

            # Log password change (without storing the actual password)
            await self.log_admin_action(
                action_type="user_password_updated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "password_strength_validated": True
                }
            )

            self.logger.info(f"Password updated for user {user.email} by admin {admin_user.email}")
            return True

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_password_update_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to update password for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )

    async def activate_user(
        self,
        user_id: UUID,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """Activate a user with permission checks."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "activate_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        try:
            user.is_active = True
            self.db.commit()
            self.db.refresh(user)

            # Log user activation
            await self.log_admin_action(
                action_type="user_activated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "user_role": user.role.value
                }
            )

            self.logger.info(f"User {user.email} activated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_activation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to activate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate user"
            )

    async def deactivate_user(
        self,
        user_id: UUID,
        admin_user: User,
        request_info: Optional[dict] = None
    ) -> User:
        """Deactivate a user with permission checks."""
        # Check admin permissions
        self._check_admin_permissions(admin_user, "deactivate_user")

        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )

        # Prevent deactivation of the last admin
        if user.role == UserRole.ADMIN:
            admin_count = self.db.query(User).filter(
                and_(User.role == UserRole.ADMIN, User.is_active == True, User.id != user_id)
            ).count()
            if admin_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active admin user"
                )

        try:
            user.is_active = False
            self.db.commit()
            self.db.refresh(user)

            # Log user deactivation
            await self.log_admin_action(
                action_type="user_deactivated",
                admin_user=admin_user,
                target_user_id=user.id,
                action_data={
                    "user_email": user.email,
                    "user_role": user.role.value
                }
            )

            self.logger.info(f"User {user.email} deactivated by admin {admin_user.email}")
            return user

        except Exception as e:
            self.db.rollback()
            await self.log_admin_action(
                action_type="user_deactivation_failed",
                admin_user=admin_user,
                target_user_id=user_id,
                action_data={
                    "reason": "database_error",
                    "error": str(e)
                },
                result="failure"
            )
            self.logger.error(f"Failed to deactivate user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate user"
            )
