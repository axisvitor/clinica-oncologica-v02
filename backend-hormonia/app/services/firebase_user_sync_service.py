"""Firebase User Synchronization Service

Handles bidirectional sync between Firebase Authentication and PostgreSQL database.
Supports user creation, linking, and updates.

SECURITY:
- Only authorized domains allowed (no public email providers)
- Custom claims validation required before user creation
- Comprehensive audit logging for all operations
- Automatic rejection of unauthorized access attempts

PERFORMANCE:
- Redis cache for verified users (5 min TTL)
- Reduces DB queries on repeated logins
"""

from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import logging
import json

from app.models.user import User, UserRole, AuthProvider
from app.services.firebase_auth_service import FirebaseAuthService
from app.config import get_firebase_security_config

logger = logging.getLogger(__name__)

# Redis cache configuration
USER_CACHE_TTL = 300  # 5 minutes
USER_CACHE_PREFIX = "user:firebase:"


async def _get_redis_client():
    """Get Redis client for caching."""
    try:
        from app.core.redis_manager import get_redis
        return await get_redis()
    except Exception as e:
        logger.debug(f"Redis not available for user cache: {e}")
        return None


def _serialize_user_for_cache(user: User) -> str:
    """Serialize user object for Redis cache."""
    return json.dumps({
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "firebase_uid": user.firebase_uid,
        "firebase_custom_claims": user.firebase_custom_claims,
        "is_active": user.is_active,
        "is_locked": getattr(user, "is_locked", False),
        "cached_at": datetime.now(timezone.utc).isoformat(),
    })


def _deserialize_user_from_cache(data: str, db) -> Optional[User]:
    """Deserialize user from Redis cache and attach to session."""
    try:
        cached = json.loads(data)
        # Fetch fresh user from DB but use cache to skip validation
        user = db.query(User).filter(User.id == cached["id"]).first()
        if user:
            logger.debug(f"User cache hit: {cached['email']}")
        return user
    except Exception as e:
        logger.debug(f"Cache deserialize failed: {e}")
        return None


async def _cache_user(redis_client, firebase_uid: str, user: User) -> bool:
    """Cache user in Redis for faster subsequent logins."""
    if not redis_client:
        return False
    try:
        cache_key = f"{USER_CACHE_PREFIX}{firebase_uid}"
        cache_data = _serialize_user_for_cache(user)
        await redis_client.setex(cache_key, USER_CACHE_TTL, cache_data)
        logger.debug(f"Cached user {user.email} for {USER_CACHE_TTL}s")
        return True
    except Exception as e:
        logger.debug(f"Failed to cache user: {e}")
        return False


class FirebaseUserSyncService:
    """
    Sync Firebase users to PostgreSQL database with security controls.

    Handles:
    - Auto-creation of users from Firebase (with strict validation)
    - Linking Firebase accounts to existing users
    - Syncing user data changes
    - Role management (ADMIN, DOCTOR only)
    - Domain validation and claims verification
    - Comprehensive audit logging

    Security Features:
    - Only authorized domains allowed
    - Custom claims validation required
    - Public domain blocking (gmail.com, yahoo.com, etc.)
    - Audit trail for all operations
    - Automatic rejection logging
    """

    def __init__(self, db: Any, firebase_service: FirebaseAuthService):
        """
        Initialize sync service with security configuration.

        Args:
            db: SQLAlchemy database session
            firebase_service: Firebase authentication service instance
        """
        self.db = db
        self.firebase_service = firebase_service
        self._security_config = get_firebase_security_config()

    async def sync_firebase_user(
        self, firebase_uid: str, firebase_data: Dict[str, Any], auto_create: bool = True
    ) -> Tuple[User, bool]:
        """
        Sync Firebase user to database with security validation.

        Process:
        0. Check Redis cache for verified user (PERFORMANCE OPTIMIZATION)
        1. Validate email domain (security check)
        2. Validate custom claims (security check)
        3. Try to find user by Firebase UID
        4. Try to find user by email (for migration)
        5. Create new user if auto_create is True and validations pass

        Args:
            firebase_uid: Firebase user ID
            firebase_data: User data from Firebase token
            auto_create: Whether to create new user if not found

        Returns:
            Tuple of (User, created_new_user)

        Raises:
            ValueError: If validation fails or user not found
            SecurityError: If domain/claims validation fails
        """
        email = firebase_data.get("email")
        if not email:
            self._log_security_event(
                "rejected",
                "missing_email",
                firebase_uid,
                None,
                error="Firebase user missing email",
            )
            raise ValueError("Firebase user missing email")

        email_lower = email.strip().lower()

        # PERFORMANCE OPTIMIZATION: Check Redis cache first
        cache_key = f"{USER_CACHE_PREFIX}{firebase_uid}"
        redis_client = await _get_redis_client()

        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    cached_user = _deserialize_user_from_cache(cached_data, self.db)
                    if cached_user and cached_user.is_active:
                        logger.info(f"Redis cache hit for user: {email_lower}")
                        # Update last sign-in timestamp (lightweight update)
                        cached_user.firebase_last_sign_in = datetime.now()
                        self.db.commit()
                        return cached_user, False
            except Exception as cache_err:
                logger.debug(f"Cache lookup failed (continuing normally): {cache_err}")

        try:
            # SECURITY VALIDATION STEP 1: Validate email domain
            if not self._validate_email_domain(email_lower):
                self._log_security_event(
                    "rejected",
                    "unauthorized_domain",
                    firebase_uid,
                    email_lower,
                    error=f"Domain not in allowed list: {email_lower.split('@')[-1]}",
                )
                raise ValueError(f"Unauthorized email domain: {email_lower}")

            # 1. Try to find by Firebase UID FIRST (before expensive claims extraction)
            user = self.db.query(User).filter(User.firebase_uid == firebase_uid).first()

            # SECURITY VALIDATION STEP 2: Validate custom claims
            # PERFORMANCE OPTIMIZATION: If user exists with cached claims, skip expensive Admin SDK call
            if user and user.firebase_custom_claims:
                # User exists with cached claims - skip Admin SDK call (8s saved!)
                logger.debug(f"Using cached claims from database for {firebase_uid}")
                custom_claims = user.firebase_custom_claims
            else:
                # No cached claims - need to extract (may call Admin SDK for new users)
                custom_claims = await self._extract_claims(
                    firebase_uid,
                    firebase_data,
                    skip_admin_sdk=False,  # Allow Admin SDK for new users only
                )

            # Validate claims for new user creation
            if auto_create and not self._validate_custom_claims(custom_claims):
                self._log_security_event(
                    "rejected",
                    "invalid_claims",
                    firebase_uid,
                    email_lower,
                    error=f"Invalid or missing role in claims: {custom_claims.get('role')}",
                )
                raise ValueError(f"Invalid role in custom claims: {custom_claims}")

            if user:
                # PERFORMANCE: Reuse claims already extracted/cached above to avoid duplicate Firebase API call
                await self._update_user_from_firebase(
                    user, firebase_data, custom_claims
                )
                self._log_sync(
                    firebase_uid, user.id, "update", "firebase_to_pg", {}, True
                )
                # Cache user for faster subsequent logins
                await _cache_user(redis_client, firebase_uid, user)
                return user, False

            # 2. Try to find by email (migration case)
            user = self.db.query(User).filter(User.email == email_lower).first()
            if user:
                await self._link_firebase_to_user(user, firebase_uid, firebase_data)
                self._log_sync(
                    firebase_uid, user.id, "link", "firebase_to_pg", {}, True
                )
                # Cache user for faster subsequent logins
                await _cache_user(redis_client, firebase_uid, user)
                return user, False

            # 3. Create new user if allowed and validated
            if not auto_create:
                raise ValueError(f"User not found: {email_lower}")

            new_user = await self._create_user_from_firebase(
                firebase_uid, firebase_data
            )
            self._log_security_event(
                "success", "user_created", firebase_uid, email_lower
            )
            self._log_sync(
                firebase_uid, new_user.id, "create", "firebase_to_pg", {}, True
            )
            # Cache new user for faster subsequent logins
            await _cache_user(redis_client, firebase_uid, new_user)
            return new_user, True

        except ValueError as e:
            # Security validation errors
            logger.error(f"Security validation failed for {firebase_uid}: {str(e)}")
            self._log_sync(
                firebase_uid, None, "sync", "firebase_to_pg", {}, False, str(e)
            )
            raise
        except Exception as e:
            logger.error(f"Error syncing Firebase user {firebase_uid}: {str(e)}")
            self._log_sync(
                firebase_uid, None, "sync", "firebase_to_pg", {}, False, str(e)
            )
            raise

    def _validate_email_domain(self, email: str) -> bool:
        """
        Validate email is from authorized domain.

        Security checks:
        - Domain must be in allowed list
        - Public domains explicitly blocked (gmail.com, yahoo.com, etc.)

        Args:
            email: Email address to validate

        Returns:
            True if domain is authorized, False otherwise
        """
        if not email or "@" not in email:
            logger.warning(f"Invalid email format: {email}")
            return False

        domain = email.split("@")[-1].lower()

        # Check if public domain is blocked
        if self._security_config["block_public_domains"]:
            if domain in self._security_config["public_domains_blocklist"]:
                logger.warning(
                    f"Rejected public domain: {domain}",
                    extra={
                        "email": email,
                        "domain": domain,
                        "reason": "public_domain_blocked",
                    },
                )
                return False

        # Check if domain is in allowed list
        if domain not in self._security_config["allowed_domains"]:
            logger.warning(
                f"Rejected unauthorized domain: {domain}",
                extra={
                    "email": email,
                    "domain": domain,
                    "reason": "domain_not_authorized",
                },
            )
            return False

        return True

    def _validate_custom_claims(self, custom_claims: Dict[str, Any]) -> bool:
        """
        Validate Firebase custom claims before user creation.

        Security checks:
        - Role must exist in claims (if required)
        - Role must be in allowed list

        Args:
            custom_claims: Custom claims from Firebase token

        Returns:
            True if claims are valid, False otherwise
        """
        if not self._security_config["require_custom_claims"]:
            return True

        role = custom_claims.get("role")

        if not role:
            logger.warning(
                "Missing role in custom claims",
                extra={"custom_claims": custom_claims, "reason": "missing_role"},
            )
            return False

        role_lower = role.lower()
        allowed_roles = [r.lower() for r in self._security_config["allowed_roles"]]

        if role_lower not in allowed_roles:
            logger.warning(
                f"Invalid role in custom claims: {role}",
                extra={
                    "role": role,
                    "allowed_roles": allowed_roles,
                    "reason": "invalid_role",
                },
            )
            return False

        return True

    async def _extract_claims(
        self,
        firebase_uid: str,
        firebase_data: Dict[str, Any],
        skip_admin_sdk: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract custom claims with fallback logic and caching.

        Fallback order:
        1. Check firebase_data['custom_claims'] (from cached token)
        2. Check top-level claims (role, roles) in firebase_data (from decoded ID token)
        3. Fetch fresh claims via Firebase Admin SDK auth.get_user() (ONLY if skip_admin_sdk=False)

        PERFORMANCE NOTE: ID tokens don't carry custom_claims, so we MUST avoid calling
        the Admin SDK on every request. The skip_admin_sdk flag prevents the expensive
        fallback when we already have cached claims in the database.

        Args:
            firebase_uid: Firebase user ID
            firebase_data: User data from Firebase token
            skip_admin_sdk: If True, skip expensive Admin SDK call (use cached DB claims)

        Returns:
            Dictionary containing custom claims with role information
        """
        claims = {}

        # Priority 1: Check custom_claims dict (cached tokens)
        if "custom_claims" in firebase_data and firebase_data["custom_claims"]:
            claims = firebase_data["custom_claims"].copy()
            logger.debug(f"Claims extracted from custom_claims dict: {claims}")
            return claims

        # Priority 2: Check top-level claims in firebase_data (decoded ID tokens)
        # Handle both 'role' (string) and 'roles' (list) claims
        if "role" in firebase_data:
            claims["role"] = firebase_data["role"]
            logger.debug(f"Claims extracted from top-level 'role': {claims}")

        if "roles" in firebase_data:
            # If roles is a list, use the first role or join them
            roles_value = firebase_data["roles"]
            if isinstance(roles_value, list) and roles_value:
                claims["role"] = roles_value[0]  # Use first role as primary
                claims["roles"] = roles_value
                logger.debug(f"Claims extracted from top-level 'roles' list: {claims}")
            elif isinstance(roles_value, str):
                claims["role"] = roles_value
                logger.debug(
                    f"Claims extracted from top-level 'roles' string: {claims}"
                )

        # If we found claims in top-level, return them
        if claims:
            return claims

        # Priority 3: Fetch fresh claims via Firebase Admin SDK (EXPENSIVE - 8s!)
        # ONLY call Admin SDK if explicitly allowed (not skipped)
        if not skip_admin_sdk:
            try:
                logger.warning(
                    f"PERFORMANCE: Fetching fresh claims for UID {firebase_uid} via Firebase Admin SDK (8s delay expected)"
                )
                from firebase_admin import auth

                user_record = auth.get_user(firebase_uid)
                if user_record.custom_claims:
                    claims = user_record.custom_claims.copy()
                    logger.info(f"Fresh claims fetched from Firebase Admin: {claims}")
                    return claims
                else:
                    logger.warning(
                        f"No custom claims found for user {firebase_uid} in Firebase Admin"
                    )
            except Exception as e:
                logger.error(
                    f"Failed to fetch claims from Firebase Admin for {firebase_uid}: {str(e)}"
                )
        else:
            logger.debug(
                f"Skipping Admin SDK call for {firebase_uid} (using cached claims from database)"
            )

        # Return empty dict if no claims found anywhere
        if not claims:
            logger.warning(f"No claims found for user {firebase_uid} in any source")
        return claims

    def _extract_role_from_claims(self, claims: Dict[str, Any]) -> str:
        """
        Extract role string from claims dictionary.

        Handles multiple claim formats:
        - claims['role'] = "admin" (single role string)
        - claims['roles'] = ["admin", "medico"] (list of roles)
        - claims['role'] = "medico" with claims['roles'] = ["medico", "doctor"]

        Args:
            claims: Claims dictionary

        Returns:
            Role string (lowercase), defaults to 'doctor' if not found
        """
        # Check single role claim first
        if "role" in claims and claims["role"]:
            role = str(claims["role"]).lower().strip()
            logger.debug(f"Extracted role from 'role' claim: {role}")
            return role

        # Check roles list claim
        if "roles" in claims and claims["roles"]:
            roles_value = claims["roles"]
            if isinstance(roles_value, list) and roles_value:
                # Use first role in list
                role = str(roles_value[0]).lower().strip()
                logger.debug(
                    f"Extracted role from 'roles' list: {role} (from {roles_value})"
                )
                return role
            elif isinstance(roles_value, str):
                role = roles_value.lower().strip()
                logger.debug(f"Extracted role from 'roles' string: {role}")
                return role

        # Default to doctor
        logger.warning("No role found in claims, defaulting to 'doctor'")
        return "doctor"

    async def _create_user_from_firebase(
        self, firebase_uid: str, firebase_data: Dict[str, Any]
    ) -> User:
        """
        Create new user from Firebase data (after security validation).

        NOTE: This method assumes email domain and claims have already been validated
        by sync_firebase_user(). Do not call directly without validation.

        Args:
            firebase_uid: Firebase user ID
            firebase_data: User data from Firebase

        Returns:
            Created User object

        Raises:
            ValueError: If validation fails (should not happen if called correctly)
        """
        email = firebase_data["email"].strip().lower()

        # Extract display name
        full_name = (
            firebase_data.get("name")
            or firebase_data.get("display_name")
            or email.split("@")[0]
        )

        # Determine role (ADMIN or DOCTOR only)
        # Extract claims with fallback logic
        custom_claims = await self._extract_claims(firebase_uid, firebase_data)
        role_str = self._extract_role_from_claims(custom_claims)

        # Map to UserRole (only ADMIN and DOCTOR supported)
        if role_str == "admin":
            role = UserRole.ADMIN
        else:
            role = UserRole.DOCTOR  # Default to doctor for all other roles

        # Create user
        new_user = User(
            email=email,
            hashed_password=None,  # No password for Firebase users
            full_name=full_name,
            role=role,
            is_active=True,
            auth_provider=AuthProvider.FIREBASE,
            firebase_uid=firebase_uid,
            firebase_email_verified=firebase_data.get("email_verified", False),
            firebase_display_name=firebase_data.get("name"),
            firebase_photo_url=firebase_data.get("picture"),
            firebase_custom_claims=custom_claims,
            firebase_created_at=self._parse_timestamp(firebase_data.get("auth_time")),
            firebase_last_sign_in=datetime.now(),
            last_firebase_sync=datetime.now(),
        )

        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        logger.info(
            f"Created Firebase user: {email} (UID: {firebase_uid}, Role: {role.value})",
            extra={"email": email, "firebase_uid": firebase_uid, "role": role.value},
        )
        return new_user

    async def _update_user_from_firebase(
        self,
        user: User,
        firebase_data: Dict[str, Any],
        cached_claims: Dict[str, Any] = None,
    ) -> bool:
        """
        Update existing user with Firebase data.

        Args:
            user: User object to update
            firebase_data: User data from Firebase
            cached_claims: Pre-extracted custom claims to avoid duplicate API calls (optional)

        Returns:
            True if user was modified
        """
        changed = False

        # Update email if changed
        new_email = firebase_data.get("email", "").strip().lower()
        if new_email and user.email != new_email:
            user.email = new_email
            changed = True
            logger.info(f"Updated email for user {user.id}: {new_email}")

        # Update display name
        new_name = firebase_data.get("name") or firebase_data.get("display_name")
        if new_name and user.firebase_display_name != new_name:
            user.firebase_display_name = new_name
            # Update full_name if not set
            if not user.full_name:
                user.full_name = new_name
            changed = True

        # Update email verification status
        email_verified = firebase_data.get("email_verified", False)
        if user.firebase_email_verified != email_verified:
            user.firebase_email_verified = email_verified
            changed = True

        # Update photo URL
        new_photo = firebase_data.get("picture")
        if new_photo and user.firebase_photo_url != new_photo:
            user.firebase_photo_url = new_photo
            changed = True

        # Update custom claims (includes role)
        # PERFORMANCE: Use cached claims if provided, otherwise extract fresh
        new_claims = (
            cached_claims
            if cached_claims is not None
            else await self._extract_claims(user.firebase_uid, firebase_data)
        )
        if user.firebase_custom_claims != new_claims:
            user.firebase_custom_claims = new_claims
            # Update role if changed in custom claims
            role_str = self._extract_role_from_claims(new_claims)
            if role_str == "admin":
                new_role = UserRole.ADMIN
            elif role_str in ["doctor", "medico"]:
                new_role = UserRole.DOCTOR
            else:
                new_role = None

            if new_role and user.role != new_role:
                user.role = new_role
                changed = True
                logger.info(f"Updated role for user {user.id}: {new_role.value}")

        # Always update last sign-in and sync timestamps
        user.firebase_last_sign_in = datetime.now()
        user.last_firebase_sync = datetime.now()

        if changed:
            try:
                self.db.commit()
                logger.info(f"Updated Firebase user: {user.email}")
            except Exception as commit_error:
                logger.error(
                    f"Failed to commit user update for {user.email}: {commit_error}"
                )
                self.db.rollback()
                raise

        return changed

    async def _link_firebase_to_user(
        self, user: User, firebase_uid: str, firebase_data: Dict[str, Any]
    ) -> bool:
        """
        Link Firebase UID to existing local user.

        This is used for migration: existing local users can be linked
        to their Firebase accounts.

        Args:
            user: Existing user object
            firebase_uid: Firebase user ID
            firebase_data: User data from Firebase

        Returns:
            True on success

        Raises:
            ValueError: If user already linked to different Firebase account
        """
        if user.firebase_uid and user.firebase_uid != firebase_uid:
            raise ValueError("User already linked to different Firebase account")

        # Link Firebase data
        user.firebase_uid = firebase_uid
        user.auth_provider = AuthProvider.FIREBASE
        user.firebase_email_verified = firebase_data.get("email_verified", False)
        user.firebase_display_name = firebase_data.get("name")
        user.firebase_photo_url = firebase_data.get("picture")
        # Extract claims with fallback logic
        user.firebase_custom_claims = await self._extract_claims(
            firebase_uid, firebase_data
        )
        user.firebase_created_at = self._parse_timestamp(firebase_data.get("auth_time"))
        user.firebase_last_sign_in = datetime.now()
        user.last_firebase_sync = datetime.now()

        self.db.commit()
        logger.info(f"Linked Firebase UID {firebase_uid} to user: {user.email}")
        return True

    def _parse_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """
        Parse Unix timestamp to datetime.

        Args:
            timestamp: Unix timestamp in seconds

        Returns:
            datetime object or None
        """
        if timestamp:
            try:
                return datetime.fromtimestamp(timestamp)
            except (ValueError, OSError):
                logger.warning(f"Invalid timestamp: {timestamp}")
        return None

    def _log_security_event(
        self,
        event_type: str,
        reason: str,
        firebase_uid: str,
        email: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """
        Enhanced audit logging for security events.

        Event types:
        - 'success': Successful operation
        - 'rejected': Security validation failed
        - 'failed': Operation error

        Args:
            event_type: Type of event (success, rejected, failed)
            reason: Reason code (unauthorized_domain, invalid_claims, user_created, etc.)
            firebase_uid: Firebase user ID
            email: User email (if available)
            error: Error message (if applicable)
        """
        if not self._security_config["enable_audit_logging"]:
            return

        log_data = {
            "event": "firebase_user_provisioning",
            "type": event_type,
            "reason": reason,
            "firebase_uid": firebase_uid,
            "email": email,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if error:
            log_data["error"] = error

        # Log with appropriate level
        if event_type == "rejected":
            logger.warning(f"User provisioning rejected: {reason}", extra=log_data)
        elif event_type == "failed":
            logger.error(f"User provisioning failed: {reason}", extra=log_data)
        else:
            logger.info(f"User provisioning success: {reason}", extra=log_data)

        # Store in audit table (if exists)
        try:
            self._store_audit_event(log_data)
        except Exception as e:
            logger.error(f"Failed to store audit event: {str(e)}")
            try:
                self.db.rollback()
            except Exception as rollback_err:
                logger.warning(f"Rollback failed during audit event storage: {rollback_err}")

    def _store_audit_event(self, event_data: Dict[str, Any]):
        """
        Store security audit event in database.

        Args:
            event_data: Event data to store
        """
        try:
            # Try to use audit_log_entries table if it exists
            from sqlalchemy import text

            query = text("""
                INSERT INTO audit_log_entries (
                    event_type, event_data, created_at
                ) VALUES (
                    :event_type, :event_data, :created_at
                )
            """)

            self.db.execute(
                query,
                {
                    "event_type": "firebase_user_provisioning",
                    "event_data": event_data,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            self.db.commit()

        except Exception as e:
            # Table might not exist - that's okay, we already logged to file
            logger.debug(f"Audit table not available: {str(e)}")

    def _log_sync(
        self,
        firebase_uid: str,
        user_id: Optional[str],
        operation: str,
        sync_direction: str,
        changes: Dict[str, Any],
        success: bool,
        error_message: Optional[str] = None,
    ):
        """
        Log sync operation to audit table.

        Args:
            firebase_uid: Firebase user ID
            user_id: PostgreSQL user ID
            operation: Operation type (create, update, link, sync)
            sync_direction: Direction (firebase_to_pg, pg_to_firebase)
            changes: Dictionary of changes made
            success: Whether operation succeeded
            error_message: Error message if failed
        """
        try:
            from app.models.user_sync_log import UserSyncLog

            log_entry = UserSyncLog(
                firebase_uid=firebase_uid,
                user_id=user_id,
                operation=operation,
                sync_direction=sync_direction,
                changes=changes,
                success=success,
                error_message=error_message,
            )

            self.db.add(log_entry)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to log sync operation: {str(e)}")
            try:
                self.db.rollback()
            except Exception as rollback_err:
                logger.warning(f"Rollback failed during sync log operation: {rollback_err}")
            # Don't raise - logging failure shouldn't break sync

    async def get_or_create_user(
        self, firebase_uid: str, firebase_data: Dict[str, Any]
    ) -> User:
        """
        Get or create user from Firebase data.

        Convenience method that always creates user if not found.

        Args:
            firebase_uid: Firebase user ID
            firebase_data: User data from Firebase

        Returns:
            User object
        """
        user, created = await self.sync_firebase_user(
            firebase_uid, firebase_data, auto_create=True
        )
        return user

    async def validate_firebase_user(
        self, firebase_uid: str, required_role: Optional[UserRole] = None
    ) -> Optional[User]:
        """
        Validate Firebase user exists and has required role.

        Args:
            firebase_uid: Firebase user ID
            required_role: Required role (optional)

        Returns:
            User object if valid, None otherwise
        """
        user = self.db.query(User).filter(User.firebase_uid == firebase_uid).first()

        if not user:
            return None

        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {firebase_uid}")
            return None

        if required_role and user.role != required_role:
            logger.warning(
                f"User {firebase_uid} lacks required role: {required_role.value}"
            )
            return None

        return user
