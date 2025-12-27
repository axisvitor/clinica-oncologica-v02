"""
Comprehensive RBAC (Role-Based Access Control) Module for Hormonia Backend.

This module provides centralized permission management with secure role definitions,
domain-based auto-provisioning, and fine-grained access control.
"""

import logging
from typing import Dict, List, Set, Optional, Tuple, Union, Any
from enum import Enum
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, field_validator
from functools import wraps
import re

from fastapi import HTTPException, status
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# =============================================================================
# PERMISSION DEFINITIONS
# =============================================================================


class Permission(Enum):
    """Comprehensive permission enumeration for RBAC system."""

    # User Management
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_LIST = "user:list"
    USER_IMPERSONATE = "user:impersonate"

    # Patient Management
    PATIENT_CREATE = "patient:create"
    PATIENT_READ = "patient:read"
    PATIENT_UPDATE = "patient:update"
    PATIENT_DELETE = "patient:delete"
    PATIENT_LIST = "patient:list"
    PATIENT_MEDICAL_RECORDS = "patient:medical_records"
    PATIENT_SENSITIVE_DATA = "patient:sensitive_data"

    # Quiz and Assessments
    QUIZ_CREATE = "quiz:create"
    QUIZ_READ = "quiz:read"
    QUIZ_UPDATE = "quiz:update"
    QUIZ_DELETE = "quiz:delete"
    QUIZ_PUBLISH = "quiz:publish"
    QUIZ_RESULTS_VIEW = "quiz:results_view"
    QUIZ_ANALYTICS = "quiz:analytics"

    # Reports and Analytics
    REPORT_CREATE = "report:create"
    REPORT_READ = "report:read"
    REPORT_UPDATE = "report:update"
    REPORT_DELETE = "report:delete"
    REPORT_EXPORT = "report:export"
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_ADVANCED = "analytics:advanced"

    # System Administration
    ADMIN_PANEL = "admin:panel"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_LOGS = "admin:logs"
    ADMIN_BACKUP = "admin:backup"
    ADMIN_RESTORE = "admin:restore"
    ADMIN_MAINTENANCE = "admin:maintenance"

    # AI and Flows
    AI_ACCESS = "ai:access"
    AI_CONFIGURE = "ai:configure"
    FLOW_CREATE = "flow:create"
    FLOW_EXECUTE = "flow:execute"
    FLOW_MANAGE = "flow:manage"

    # Templates and Content
    TEMPLATE_CREATE = "template:create"
    TEMPLATE_READ = "template:read"
    TEMPLATE_UPDATE = "template:update"
    TEMPLATE_DELETE = "template:delete"
    TEMPLATE_PUBLISH = "template:publish"

    # Messaging and Notifications
    MESSAGE_SEND = "message:send"
    MESSAGE_BROADCAST = "message:broadcast"
    NOTIFICATION_MANAGE = "notification:manage"

    # API and Integration
    API_ACCESS = "api:access"
    API_RATE_LIMIT_BYPASS = "api:rate_limit_bypass"
    WEBHOOK_MANAGE = "webhook:manage"
    INTEGRATION_MANAGE = "integration:manage"


class SecurityLevel(Enum):
    """Security levels for permission validation."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    VERIFIED = "verified"
    PRIVILEGED = "privileged"
    RESTRICTED = "restricted"


# =============================================================================
# ROLE DEFINITIONS WITH SECURE DEFAULTS
# =============================================================================


class RoleDefinition(BaseModel):
    """Secure role definition with permissions and constraints."""

    name: str
    permissions: Set[Permission]
    security_level: SecurityLevel
    description: str
    is_default: bool = False
    requires_verification: bool = True
    max_auto_grant_duration: Optional[timedelta] = None
    allowed_domains: Optional[List[str]] = None
    restricted_domains: Optional[List[str]] = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v):
        """Ensure permissions are valid."""
        if not v:
            raise ValueError("Role must have at least one permission")
        return v

    def can_auto_grant(self, email_domain: str) -> bool:
        """Check if role can be auto-granted based on email domain."""
        if not self.allowed_domains:
            return False

        if self.restricted_domains and email_domain in self.restricted_domains:
            return False

        return email_domain in self.allowed_domains


# Secure role definitions with principle of least privilege
ROLE_DEFINITIONS: Dict[UserRole, RoleDefinition] = {
    UserRole.ADMIN: RoleDefinition(
        name="Administrator",
        permissions={
            Permission.USER_CREATE,
            Permission.USER_READ,
            Permission.USER_UPDATE,
            Permission.USER_DELETE,
            Permission.USER_LIST,
            Permission.PATIENT_CREATE,
            Permission.PATIENT_READ,
            Permission.PATIENT_UPDATE,
            Permission.PATIENT_DELETE,
            Permission.PATIENT_LIST,
            Permission.PATIENT_MEDICAL_RECORDS,
            Permission.PATIENT_SENSITIVE_DATA,
            Permission.QUIZ_CREATE,
            Permission.QUIZ_READ,
            Permission.QUIZ_UPDATE,
            Permission.QUIZ_DELETE,
            Permission.QUIZ_PUBLISH,
            Permission.QUIZ_RESULTS_VIEW,
            Permission.QUIZ_ANALYTICS,
            Permission.REPORT_CREATE,
            Permission.REPORT_READ,
            Permission.REPORT_UPDATE,
            Permission.REPORT_EXPORT,
            Permission.ANALYTICS_VIEW,
            Permission.ANALYTICS_ADVANCED,
            Permission.ADMIN_PANEL,
            Permission.ADMIN_SETTINGS,
            Permission.ADMIN_LOGS,
            Permission.AI_ACCESS,
            Permission.AI_CONFIGURE,
            Permission.FLOW_CREATE,
            Permission.FLOW_EXECUTE,
            Permission.FLOW_MANAGE,
            Permission.TEMPLATE_CREATE,
            Permission.TEMPLATE_READ,
            Permission.TEMPLATE_UPDATE,
            Permission.TEMPLATE_DELETE,
            Permission.TEMPLATE_PUBLISH,
            Permission.MESSAGE_SEND,
            Permission.MESSAGE_BROADCAST,
            Permission.NOTIFICATION_MANAGE,
            Permission.API_ACCESS,
            Permission.WEBHOOK_MANAGE,
            Permission.INTEGRATION_MANAGE,
        },
        security_level=SecurityLevel.PRIVILEGED,
        description="Administrative access with management capabilities",
        requires_verification=True,
        allowed_domains=["hormonia.io", "admin.local", "clinica.med.br"],
        max_auto_grant_duration=timedelta(hours=24),  # Require re-verification
    ),
    UserRole.DOCTOR: RoleDefinition(
        name="Doctor",
        permissions={
            Permission.USER_READ,
            Permission.PATIENT_CREATE,
            Permission.PATIENT_READ,
            Permission.PATIENT_UPDATE,
            Permission.PATIENT_LIST,
            Permission.PATIENT_MEDICAL_RECORDS,
            Permission.PATIENT_SENSITIVE_DATA,
            Permission.QUIZ_CREATE,
            Permission.QUIZ_READ,
            Permission.QUIZ_UPDATE,
            Permission.QUIZ_RESULTS_VIEW,
            Permission.QUIZ_ANALYTICS,
            Permission.REPORT_CREATE,
            Permission.REPORT_READ,
            Permission.REPORT_EXPORT,
            Permission.ANALYTICS_VIEW,
            Permission.AI_ACCESS,
            Permission.FLOW_EXECUTE,
            Permission.TEMPLATE_READ,
            Permission.TEMPLATE_CREATE,
            Permission.MESSAGE_SEND,
            Permission.API_ACCESS,
        },
        security_level=SecurityLevel.VERIFIED,
        description="Medical professional with patient care access",
        requires_verification=True,
        allowed_domains=["med.br", "saude.gov.br", "crm.org.br", "hospital.com.br"],
    ),
}


# =============================================================================
# SECURE ROLE DETERMINATION
# =============================================================================


class SecureRoleDeterminer:
    """Secure role determination with domain validation and audit logging."""

    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []

    def determine_role_from_email(
        self,
        email: str,
        identity_claims: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[UserRole, str]:
        """
        Securely determine user role based on email domain and custom identity claims.

        Args:
            email: User email address
            identity_claims: Claims from identity provider token (Firebase)
            request_context: Additional request context for auditing

        Returns:
            Tuple of (UserRole, reason)
        """
        email = email.strip().lower()
        domain = self._extract_domain(email)

        audit_entry = {
            "timestamp": datetime.now(timezone.utc),
            "email": email,
            "domain": domain,
            "identity_claims": identity_claims or {},
            "request_context": request_context or {},
        }

        try:
            # Priority 1: Explicit role from custom claims
            if identity_claims:
                explicit_role = self._get_role_from_claims(identity_claims)
                if explicit_role:
                    audit_entry.update(
                        {
                            "role_assigned": explicit_role,
                            "assignment_reason": "identity_explicit_claim",
                            "security_level": "high",
                        }
                    )
                    self.audit_log.append(audit_entry)
                    return explicit_role, "Assigned from identity provider claims"

            # Priority 2: Domain-based assignment with restrictions
            domain_role = self._get_role_from_domain(domain, email)
            if domain_role:
                audit_entry.update(
                    {
                        "role_assigned": domain_role,
                        "assignment_reason": "domain_based",
                        "security_level": "medium",
                    }
                )
                self.audit_log.append(audit_entry)
                return domain_role, f"Auto-assigned based on domain: {domain}"

            # Priority 3: Default role (most restrictive)
            default_role = UserRole.DOCTOR
            audit_entry.update(
                {
                    "role_assigned": default_role,
                    "assignment_reason": "default_fallback",
                    "security_level": "low",
                }
            )
            self.audit_log.append(audit_entry)

            logger.warning(
                f"User {email} assigned default role due to unrecognized domain: {domain}"
            )
            return default_role, "Default role assigned - domain not recognized"

        except Exception as e:
            audit_entry.update(
                {
                    "role_assigned": UserRole.DOCTOR,
                    "assignment_reason": "error_fallback",
                    "error": str(e),
                    "security_level": "critical",
                }
            )
            self.audit_log.append(audit_entry)

            logger.error(f"Error determining role for {email}: {e}")
            return UserRole.DOCTOR, f"Error occurred - assigned default role: {e}"

    def _extract_domain(self, email: str) -> str:
        """Safely extract domain from email."""
        local_part, sep, domain = email.partition("@")
        if not sep or not local_part.strip():
            raise ValueError("Invalid email format")

        domain = domain.lower()

        # Validate domain format
        if not re.match(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", domain):
            raise ValueError(f"Invalid domain format: {domain}")

        return domain

    def _get_role_from_claims(self, claims: Dict[str, Any]) -> Optional[UserRole]:
        """Extract role from identity claims with validation."""
        try:
            user_metadata = claims.get("user_metadata", {}) or {}
            app_metadata = claims.get("app_metadata", {}) or {}

            role_sources = [
                user_metadata.get("role"),
                user_metadata.get("user_role"),
                app_metadata.get("role"),
                app_metadata.get("user_role"),
                claims.get("role"),
            ]

            for role_value in role_sources:
                if role_value:
                    # Try to parse as UserRole enum
                    try:
                        if isinstance(role_value, str):
                            lowered = role_value.strip().lower()
                            try:
                                return UserRole(lowered)
                            except ValueError:
                                try:
                                    return UserRole[role_value.strip().upper()]
                                except KeyError:
                                    logger.warning(
                                        f"Invalid role in identity claims: {role_value}"
                                    )
                                    continue
                        elif isinstance(role_value, UserRole):
                            return role_value
                    except (ValueError, KeyError):
                        logger.warning(f"Invalid role in identity claims: {role_value}")
                        continue

            return None

        except Exception as e:
            logger.error(f"Error parsing identity claims: {e}")
            return None

    def _get_role_from_domain(self, domain: str, email: str) -> Optional[UserRole]:
        """Determine role based on email domain with security validation."""
        # Check each role to see if domain is allowed
        for role, definition in ROLE_DEFINITIONS.items():
            if definition.can_auto_grant(domain):
                # Additional security checks for privileged roles
                if definition.security_level in [
                    SecurityLevel.PRIVILEGED,
                    SecurityLevel.RESTRICTED,
                ]:
                    # Log privileged role auto-assignment
                    logger.warning(
                        f"Privileged role {role} auto-assigned to {email} "
                        f"based on domain {domain} - requires verification"
                    )

                return role

        return None

    def validate_role_assignment(
        self,
        user_email: str,
        proposed_role: UserRole,
        current_user_role: Optional[UserRole] = None,
    ) -> Tuple[bool, str]:
        """
        Validate if a role assignment is allowed.

        Args:
            user_email: Email of user being assigned role
            proposed_role: Role being assigned
            current_user_role: Role of user making the assignment

        Returns:
            Tuple of (is_valid, reason)
        """
        try:
            domain = self._extract_domain(user_email)
            role_def = ROLE_DEFINITIONS.get(proposed_role)

            if not role_def:
                return False, f"Invalid role: {proposed_role}"

            # Check if current user has permission to assign this role
            if current_user_role:
                if not self._can_assign_role(current_user_role, proposed_role):
                    return (
                        False,
                        f"Insufficient permissions to assign role {proposed_role}",
                    )

            # Check domain restrictions
            if role_def.restricted_domains and domain in role_def.restricted_domains:
                return False, f"Domain {domain} is restricted for role {proposed_role}"

            # Check if domain is allowed for auto-assignment
            if role_def.allowed_domains and domain not in role_def.allowed_domains:
                if role_def.security_level in {
                    SecurityLevel.PRIVILEGED,
                    SecurityLevel.RESTRICTED,
                }:
                    return (
                        False,
                        f"Domain {domain} is not approved for restricted role {proposed_role.value}",
                    )
                logger.warning(
                    f"Manual role assignment for {user_email}: domain {domain} not in allowed list"
                )

            return True, "Role assignment valid"

        except Exception as e:
            return False, f"Validation error: {e}"

    def _can_assign_role(self, assigner_role: UserRole, target_role: UserRole) -> bool:
        """Check if one role can assign another role."""
        assigner_def = ROLE_DEFINITIONS.get(assigner_role)
        target_def = ROLE_DEFINITIONS.get(target_role)

        if not assigner_def or not target_def:
            return False

        # Admin can assign non-admin roles
        if assigner_role == UserRole.ADMIN and target_role != UserRole.ADMIN:
            return True

        return False

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        return self.audit_log[-limit:]


# =============================================================================
# PERMISSION CHECKER
# =============================================================================


class PermissionChecker:
    """Centralized permission checking with context awareness."""

    @staticmethod
    def _normalize_permissions(role_def) -> set[Permission]:
        """Return permissions as Permission enum instances."""
        if not role_def or not role_def.permissions:
            return set()
        normalized = set()
        for perm in role_def.permissions:
            if isinstance(perm, Permission):
                normalized.add(perm)
                continue
            try:
                normalized.add(Permission(perm))
            except ValueError:
                logger.warning("Unknown permission value: %s", perm)
        return normalized

    @staticmethod
    def has_permission(user_role: UserRole, permission: Permission) -> bool:
        """Check if a role has a specific permission."""
        role_def = ROLE_DEFINITIONS.get(user_role)
        if not role_def:
            return False
        return permission in PermissionChecker._normalize_permissions(role_def)

    @staticmethod
    def has_any_permission(user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if a role has any of the specified permissions."""
        return any(
            PermissionChecker.has_permission(user_role, perm) for perm in permissions
        )

    @staticmethod
    def has_all_permissions(user_role: UserRole, permissions: List[Permission]) -> bool:
        """Check if a role has all of the specified permissions."""
        return all(
            PermissionChecker.has_permission(user_role, perm) for perm in permissions
        )

    @staticmethod
    def get_user_permissions(user_role: UserRole) -> Set[Permission]:
        """Get all permissions for a user role."""
        role_def = ROLE_DEFINITIONS.get(user_role)
        return PermissionChecker._normalize_permissions(role_def)

    @staticmethod
    def can_access_resource(
        user_role: UserRole,
        resource_type: str,
        action: str,
        resource_owner_role: Optional[UserRole] = None,
    ) -> bool:
        """
        Check if user can access a specific resource with context.

        Args:
            user_role: Role of user requesting access
            resource_type: Type of resource (patient, user, quiz, etc.)
            action: Action being performed (read, write, delete, etc.)
            resource_owner_role: Role of resource owner (for hierarchical checks)
        """
        # Map resource actions to permissions
        permission_map = {
            ("user", "create"): Permission.USER_CREATE,
            ("user", "read"): Permission.USER_READ,
            ("user", "update"): Permission.USER_UPDATE,
            ("user", "delete"): Permission.USER_DELETE,
            ("patient", "create"): Permission.PATIENT_CREATE,
            ("patient", "read"): Permission.PATIENT_READ,
            ("patient", "update"): Permission.PATIENT_UPDATE,
            ("patient", "delete"): Permission.PATIENT_DELETE,
            ("quiz", "create"): Permission.QUIZ_CREATE,
            ("quiz", "read"): Permission.QUIZ_READ,
            ("quiz", "update"): Permission.QUIZ_UPDATE,
            ("quiz", "delete"): Permission.QUIZ_DELETE,
            # Add more mappings as needed
        }

        required_permission = permission_map.get((resource_type, action))
        if not required_permission:
            logger.warning(f"Unknown resource action: {resource_type}:{action}")
            return False

        has_base_permission = PermissionChecker.has_permission(
            user_role, required_permission
        )

        # Additional hierarchical checks
        if resource_owner_role and has_base_permission:
            # Users generally can't act on resources owned by higher-privilege users
            user_def = ROLE_DEFINITIONS.get(user_role)
            owner_def = ROLE_DEFINITIONS.get(resource_owner_role)
            user_level = user_def.security_level if user_def else SecurityLevel.PUBLIC
            owner_level = (
                owner_def.security_level if owner_def else SecurityLevel.PUBLIC
            )

            level_hierarchy = {
                SecurityLevel.PUBLIC: 0,
                SecurityLevel.AUTHENTICATED: 1,
                SecurityLevel.VERIFIED: 2,
                SecurityLevel.PRIVILEGED: 3,
                SecurityLevel.RESTRICTED: 4,
            }

            if level_hierarchy.get(user_level, 0) < level_hierarchy.get(owner_level, 0):
                return False

        return has_base_permission


# =============================================================================
# DECORATORS FOR PERMISSION CHECKING
# =============================================================================


def require_permission(permission: Permission):
    """Decorator to require specific permission for endpoint access."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from function arguments
            user = None
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                    break

            # Check kwargs for user
            if not user:
                user = kwargs.get("current_user") or kwargs.get("user")

            if not user or not hasattr(user, "role"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not PermissionChecker.has_permission(user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission required: {permission.value}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(permissions: List[Permission]):
    """Decorator to require any of the specified permissions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from function arguments
            user = None
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                    break

            if not user:
                user = kwargs.get("current_user") or kwargs.get("user")

            if not user or not hasattr(user, "role"):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not PermissionChecker.has_any_permission(user.role, permissions):
                permission_names = [p.value for p in permissions]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"One of these permissions required: {', '.join(permission_names)}",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

# Create global instances for use throughout the application
role_determiner = SecureRoleDeterminer()
permission_checker = PermissionChecker()


# Export key functions for backward compatibility
def determine_user_role(
    email: str, identity_claims: Optional[Dict[str, Any]] = None
) -> Tuple[UserRole, str]:
    """Backward compatible function for role determination."""
    return role_determiner.determine_role_from_email(email, identity_claims)


def has_permission(user_role: UserRole, permission: Permission) -> bool:
    """Backward compatible function for permission checking."""
    return permission_checker.has_permission(user_role, permission)


# =============================================================================
# BACKWARD COMPATIBILITY WRAPPER
# =============================================================================


class RolePermissions:
    """
    Backward compatibility wrapper for PermissionChecker.

    This class provides a static interface matching the legacy RolePermissions
    API while delegating to the new PermissionChecker implementation.

    Note: This is a compatibility shim. New code should use PermissionChecker directly.
    """

    @staticmethod
    def has_permission(user_role: Union[str, UserRole], permission: Permission) -> bool:
        """
        Check if a role has a specific permission.

        Args:
            user_role: Role as string or UserRole enum
            permission: Permission to check

        Returns:
            True if role has permission, False otherwise
        """
        # Convert string to UserRole enum if needed
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role.lower())
            except ValueError:
                logger.warning(f"Invalid role string: {user_role}")
                return False

        return permission_checker.has_permission(user_role, permission)

    @staticmethod
    def has_any_permission(
        user_role: Union[str, UserRole], permissions: List[Permission]
    ) -> bool:
        """
        Check if a role has any of the specified permissions.

        Args:
            user_role: Role as string or UserRole enum
            permissions: List of permissions to check

        Returns:
            True if role has any permission, False otherwise
        """
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role.lower())
            except ValueError:
                logger.warning(f"Invalid role string: {user_role}")
                return False

        return permission_checker.has_any_permission(user_role, permissions)

    @staticmethod
    def has_all_permissions(
        user_role: Union[str, UserRole], permissions: List[Permission]
    ) -> bool:
        """
        Check if a role has all of the specified permissions.

        Args:
            user_role: Role as string or UserRole enum
            permissions: List of permissions to check

        Returns:
            True if role has all permissions, False otherwise
        """
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role.lower())
            except ValueError:
                logger.warning(f"Invalid role string: {user_role}")
                return False

        return permission_checker.has_all_permissions(user_role, permissions)

    @staticmethod
    def get_user_permissions(user_role: Union[str, UserRole]) -> Set[Permission]:
        """
        Get all permissions for a user role.

        Args:
            user_role: Role as string or UserRole enum

        Returns:
            Set of permissions for the role
        """
        if isinstance(user_role, str):
            try:
                user_role = UserRole(user_role.lower())
            except ValueError:
                logger.warning(f"Invalid role string: {user_role}")
                return set()

        return permission_checker.get_user_permissions(user_role)
