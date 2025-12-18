"""
User Provisioning Service - Automatic user provisioning from Firebase Auth.

This service handles:
- Auto-provisioning users from identity provider authentication (Firebase)
- Email domain validation for access control
- Default role assignment based on domain
- Integration with existing UserRepository
"""

import logging
import secrets
from typing import Optional, Dict, Any

from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.utils.security import get_password_hash

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """
    Service for automatic user provisioning from Firebase (or compatible) identity providers.

    Features:
    - Email domain whitelist validation
    - Automatic role assignment
    - Integration with local user database
    - Audit logging for security
    """

    # Authorized email domains for auto-provisioning
    AUTHORIZED_DOMAINS = ["oncologia.com", "hospital.local", "neoplasiaslitoral.com"]

    def __init__(self, user_repository: UserRepository):
        """
        Initialize user provisioning service.

        Args:
            user_repository: Repository for user database operations
        """
        self.user_repository = user_repository

    async def provision_user(
        self, email: str, identity_profile: Dict[str, Any]
    ) -> Optional[User]:
        """
        Provision user from identity provider authentication data.

        Process:
        1. Validate email domain
        2. Determine appropriate role
        3. Create local user record
        4. Return created user

        Args:
            email: User email address
            identity_profile: Identity provider user data dict

        Returns:
            Created User object or None if provisioning fails

        Raises:
            ValueError: If email domain is not authorized
        """
        # Normalize email
        email_lower = email.strip().lower()

        # Validate email domain
        if not self.validate_email_domain(email_lower):
            logger.warning(f"Unauthorized domain attempt: {email_lower}")
            raise ValueError(
                "Access denied. Only authorized medical professionals can access this system."
            )

        # Determine role
        role = self.assign_default_role(email_lower, identity_profile)

        # Extract metadata
        metadata = identity_profile.get("user_metadata") or {}
        full_name = metadata.get("full_name") or email_lower

        # Generate secure random password (not used, but required by schema)
        random_password = secrets.token_urlsafe(32)
        hashed_password = get_password_hash(random_password)

        # Create user data
        user_data = {
            "email": email_lower,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "role": role,
            "is_active": True,
            "auto_provisioned": True,  # Track auto-provisioned users
            "specialization": "Oncologia",  # Default specialization for doctors
        }

        try:
            # Create user in local database
            user = self.user_repository.create(user_data)
            logger.info(f"Auto-provisioned {role} user: {email_lower}")
            return user

        except Exception as e:
            logger.error(f"Failed to provision user {email_lower}: {e}")
            return None

    def validate_email_domain(self, email: str) -> bool:
        """
        Validate email domain against whitelist.

        Args:
            email: Email address to validate

        Returns:
            True if domain is authorized, False otherwise
        """
        if "@" not in email:
            return False

        domain = email.split("@")[-1].lower()

        # Check against authorized domains
        is_authorized = domain in self.AUTHORIZED_DOMAINS

        if not is_authorized:
            logger.warning(f"Domain not authorized: {domain}")

        return is_authorized

    def assign_default_role(
        self, email: str, identity_profile: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Assign default role based on email domain and identity metadata.

        Rules:
        - Admin role CANNOT be auto-provisioned (security)
        - Patient role is REJECTED (patients use WhatsApp/Quiz only)
        - Default role is DOCTOR for medical professionals

        Args:
            email: User email address
            identity_profile: Optional identity user data with metadata

        Returns:
            Role string (always "doctor" for auto-provisioning)
        """
        # Check identity provider metadata for role hint
        if identity_profile:
            metadata = identity_profile.get("user_metadata") or {}
            identity_role = metadata.get("role", "").lower()

            # Admin role cannot be auto-provisioned (security policy)
            if identity_role == "admin":
                logger.warning(
                    f"Admin role requested for {email} - denied (manual creation required)"
                )
                return UserRole.DOCTOR  # Always downgrade to doctor

            # Patient role is explicitly rejected
            if identity_role == "patient":
                logger.error(
                    f"Patient role attempt for {email} - patients don't have system access"
                )
                raise ValueError(
                    "Patients access the system via WhatsApp and Quiz links only."
                )

        # Default role for all auto-provisioned users
        logger.info(f"Assigning default DOCTOR role to {email}")
        return UserRole.DOCTOR

    async def update_user_from_identity(
        self, user: User, identity_profile: Dict[str, Any]
    ) -> User:
        """
        Update existing user with latest identity provider data.

        Args:
            user: Existing User object
            identity_profile: Latest identity provider user data

        Returns:
            Updated User object
        """
        try:
            metadata = identity_profile.get("user_metadata") or {}

            # Update full name if changed
            new_full_name = metadata.get("full_name")
            if new_full_name and new_full_name != user.full_name:
                user.full_name = new_full_name
                logger.info(f"Updated full name for {user.email}")

            # Commit changes
            self.user_repository.update(user.id, {"full_name": user.full_name})

            return user

        except Exception as e:
            logger.error(f"Failed to update user from identity provider: {e}")
            return user

    # Backward compatibility alias
    async def update_user_from_supabase(
        self, user: User, supabase_user: Dict[str, Any]
    ) -> User:
        return await self.update_user_from_identity(user, supabase_user)


# Global service instance (initialized with repository)
_user_provisioning_service: Optional[UserProvisioningService] = None


def get_user_provisioning_service(
    user_repository: UserRepository,
) -> UserProvisioningService:
    """
    Get or create global user provisioning service instance.

    Args:
        user_repository: UserRepository instance

    Returns:
        UserProvisioningService instance
    """
    global _user_provisioning_service
    if _user_provisioning_service is None:
        _user_provisioning_service = UserProvisioningService(user_repository)
    return _user_provisioning_service
