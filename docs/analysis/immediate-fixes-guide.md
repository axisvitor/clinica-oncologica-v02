# Immediate Fixes Implementation Guide

**Priority:** BLOCKER (Before Production Deployment)
**Estimated Effort:** 6.5 days
**Impact:** Security Hardening + HIPAA Compliance

---

## Fix 1: Redis Session Encryption (SEC-001)

**Severity:** CRITICAL
**Effort:** 2 days
**Files:** `redis_manager.py`, `auth.py`, `unified_cache.py`

### Step 1: Install Dependencies

```bash
pip install cryptography==41.0.7
```

### Step 2: Generate Encryption Key

```bash
# Run once to generate key, add to .env
python -c "from cryptography.fernet import Fernet; print(f'REDIS_ENCRYPTION_KEY={Fernet.generate_key().decode()}')"
```

### Step 3: Create Encrypted Redis Wrapper

**File:** `backend-hormonia/app/core/encrypted_redis.py`

```python
"""Encrypted Redis Manager - Transparent encryption for session data"""
import logging
from typing import Optional, Any
from cryptography.fernet import Fernet, InvalidToken
import redis.asyncio as redis
import json

from app.config import settings

logger = logging.getLogger(__name__)


class EncryptedRedisClient:
    """
    Transparent encryption wrapper for Redis operations.

    Encrypts all values before storage, decrypts on retrieval.
    Keys are NOT encrypted to preserve Redis pattern matching.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

        # Initialize Fernet cipher
        encryption_key = getattr(settings, 'REDIS_ENCRYPTION_KEY', None)
        if not encryption_key:
            logger.error("REDIS_ENCRYPTION_KEY not configured - encryption DISABLED!")
            self.cipher = None
        else:
            try:
                self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
                logger.info("Redis encryption ENABLED")
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
                self.cipher = None

    def _encrypt(self, value: Any) -> bytes:
        """Encrypt value for storage"""
        if self.cipher is None:
            # Fallback: store unencrypted (log warning)
            logger.warning("Storing unencrypted data in Redis (encryption disabled)")
            return str(value).encode()

        # Serialize to JSON for complex types
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        elif not isinstance(value, (str, bytes)):
            value = str(value)

        # Convert to bytes
        value_bytes = value.encode() if isinstance(value, str) else value

        # Encrypt
        return self.cipher.encrypt(value_bytes)

    def _decrypt(self, encrypted_value: bytes) -> Optional[str]:
        """Decrypt value from storage"""
        if not encrypted_value:
            return None

        if self.cipher is None:
            # Fallback: assume unencrypted
            logger.warning("Reading potentially unencrypted data from Redis")
            return encrypted_value.decode() if isinstance(encrypted_value, bytes) else str(encrypted_value)

        try:
            decrypted = self.cipher.decrypt(encrypted_value)
            return decrypted.decode()
        except InvalidToken:
            logger.error("Redis decryption failed - invalid token or corrupted data")
            return None
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None

    # -------------------------------------------------------------------------
    # Encrypted Redis Operations
    # -------------------------------------------------------------------------

    async def set(self, key: str, value: Any, ex: Optional[int] = None, **kwargs) -> bool:
        """Set encrypted value with optional expiration"""
        encrypted = self._encrypt(value)
        return await self.redis.set(key, encrypted, ex=ex, **kwargs)

    async def get(self, key: str) -> Optional[str]:
        """Get and decrypt value"""
        encrypted = await self.redis.get(key)
        if encrypted is None:
            return None
        return self._decrypt(encrypted)

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        """Set encrypted value with expiration (seconds)"""
        encrypted = self._encrypt(value)
        return await self.redis.setex(key, seconds, encrypted)

    async def incr(self, key: str) -> int:
        """
        Increment counter (NOT encrypted - counters use plaintext).

        Rationale: Encryption breaks INCR atomicity. Use only for:
        - Rate limiting counters
        - Session counters
        - Non-sensitive numeric values
        """
        return await self.redis.incr(key)

    async def delete(self, *keys: str) -> int:
        """Delete keys (works with encrypted values)"""
        return await self.redis.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Check key existence"""
        return await self.redis.exists(*keys)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on key"""
        return await self.redis.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get time-to-live for key"""
        return await self.redis.ttl(key)

    # -------------------------------------------------------------------------
    # Advanced Operations (with encryption)
    # -------------------------------------------------------------------------

    async def hset(self, name: str, key: str, value: Any) -> int:
        """Set hash field with encrypted value"""
        encrypted = self._encrypt(value)
        return await self.redis.hset(name, key, encrypted)

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get and decrypt hash field"""
        encrypted = await self.redis.hget(name, key)
        if encrypted is None:
            return None
        return self._decrypt(encrypted)

    async def hgetall(self, name: str) -> dict:
        """Get all hash fields (decrypted)"""
        encrypted_hash = await self.redis.hgetall(name)
        if not encrypted_hash:
            return {}

        decrypted = {}
        for field, encrypted_value in encrypted_hash.items():
            decrypted[field] = self._decrypt(encrypted_value)
        return decrypted

    async def ping(self) -> bool:
        """Health check (passthrough)"""
        return await self.redis.ping()


# Factory function for easy integration
def create_encrypted_redis_client(redis_client: redis.Redis) -> EncryptedRedisClient:
    """Create encrypted Redis client wrapper"""
    return EncryptedRedisClient(redis_client)
```

### Step 4: Update Redis Manager

**File:** `backend-hormonia/app/core/redis_manager.py`

```python
# Add import
from app.core.encrypted_redis import create_encrypted_redis_client

class RedisManager:
    # ... existing code ...

    async def get_encrypted_client(self) -> EncryptedRedisClient:
        """
        Get encrypted Redis client for sensitive data.

        Use this for:
        - User session data
        - Authentication tokens
        - Personal information (PII/PHI)

        Use regular client for:
        - Rate limit counters
        - Public cache data
        - Non-sensitive metrics
        """
        async_client = await self.get_async_client()
        return create_encrypted_redis_client(async_client)
```

### Step 5: Update AuthService to Use Encryption

**File:** `backend-hormonia/app/services/auth.py`

```python
class AuthService:
    def __init__(self, db: Session, user_repository: UserRepository, redis_client=None):
        self.db = db
        self.repository = user_repository

        # CHANGE: Use encrypted client for sensitive data
        if redis_client:
            from app.core.encrypted_redis import create_encrypted_redis_client
            self.redis = create_encrypted_redis_client(redis_client)
            logger.info("AuthService using ENCRYPTED Redis client")
        else:
            self.redis = None
            logger.warning("AuthService running without Redis")

        # ... rest of init ...

    # Rate limit counters DON'T need encryption (numeric only)
    async def _record_failed_attempt_redis(self, email: str, client_ip: Optional[str] = None):
        """Record failed attempt (counters use plaintext INCR)"""
        # SAFE: INCR operations on counters (non-sensitive)
        await self.redis.incr(...)  # This uses plaintext

    # User data DOES need encryption
    async def _cache_user_session(self, user: User, token_hash: str):
        """Cache encrypted user session data"""
        session_data = {
            "user_id": str(user.id),
            "email": user.email,  # PHI - needs encryption
            "role": user.role,
            "cached_at": datetime.utcnow().isoformat()
        }

        # SECURE: Encrypted storage
        await self.redis.set(
            f"session:user:{token_hash}",
            json.dumps(session_data),  # Encrypted by wrapper
            ex=1800  # 30 min TTL
        )
        logger.debug(f"Cached ENCRYPTED user session: {user.id}")
```

### Step 6: Update Environment Configuration

**File:** `.env`

```bash
# Add encryption key (REQUIRED for production)
REDIS_ENCRYPTION_KEY=<output from Step 2>

# Enable encryption in settings
REDIS_ENABLE_ENCRYPTION=true
```

### Step 7: Update Settings

**File:** `backend-hormonia/app/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Redis Encryption
    REDIS_ENCRYPTION_KEY: Optional[str] = None
    REDIS_ENABLE_ENCRYPTION: bool = True

    @validator('REDIS_ENCRYPTION_KEY')
    def validate_encryption_key(cls, v, values):
        """Validate encryption key in production"""
        env = values.get('ENVIRONMENT', 'development')

        if env == 'production' and not v:
            raise ValueError(
                "REDIS_ENCRYPTION_KEY is REQUIRED in production for HIPAA compliance"
            )

        if v and len(v.encode()) != 44:  # Fernet key is always 44 bytes base64
            raise ValueError(
                "Invalid REDIS_ENCRYPTION_KEY format (must be 44-byte base64 Fernet key)"
            )

        return v
```

---

## Fix 2: Persistent Token Blacklist (SEC-002)

**Severity:** CRITICAL
**Effort:** 1 day
**Files:** `auth.py`

### Implementation

**File:** `backend-hormonia/app/services/auth.py`

```python
import hashlib
import time

class AuthService:
    # ... existing code ...

    async def blacklist_token(
        self,
        token: str,
        exp_timestamp: Optional[int] = None,
        reason: str = "logout"
    ) -> None:
        """
        Blacklist JWT token in Redis until expiration.

        Args:
            token: JWT token to blacklist
            exp_timestamp: Token expiration timestamp (Unix time)
            reason: Reason for blacklisting (logout, security, etc.)
        """
        if not token:
            return

        token = token.replace('Bearer ', '').strip()

        # Hash token for storage (don't store raw tokens)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Calculate remaining TTL
        if exp_timestamp:
            remaining_ttl = max(0, exp_timestamp - int(time.time()))
        else:
            # Default to 30 minutes (ACCESS_TOKEN_EXPIRE_MINUTES)
            remaining_ttl = 30 * 60

        if remaining_ttl > 0 and self.redis:
            # Store in Redis with automatic expiration
            blacklist_data = {
                "reason": reason,
                "blacklisted_at": datetime.utcnow().isoformat(),
                "expires_at": datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None
            }

            await self.redis.setex(
                f"blacklist:token:{token_hash}",
                remaining_ttl,
                json.dumps(blacklist_data)  # Encrypted by wrapper
            )

            logger.info(f"Token blacklisted (reason: {reason}, TTL: {remaining_ttl}s)")
        else:
            # Fallback to in-memory (for backward compatibility)
            self._blacklisted_tokens.add(token)
            logger.warning("Token blacklisted in-memory (Redis unavailable)")

    async def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted.

        Args:
            token: JWT token to check

        Returns:
            True if blacklisted, False otherwise
        """
        if not token:
            return False

        token = token.replace('Bearer ', '').strip()
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Check Redis first
        if self.redis:
            exists = await self.redis.exists(f"blacklist:token:{token_hash}")
            if exists:
                logger.debug(f"Token found in Redis blacklist")
                return True

        # Fallback to in-memory
        if token in self._blacklisted_tokens:
            logger.debug(f"Token found in in-memory blacklist")
            return True

        return False

    def verify_token(self, token: str, token_type: str = "access") -> Optional[TokenData]:
        """
        Verify JWT token (updated to check blacklist).
        """
        if not token:
            return None

        token = token.replace('Bearer ', '').strip()

        # CHECK BLACKLIST FIRST (before expensive JWT verification)
        import asyncio
        try:
            # Run async check in sync context
            is_blacklisted = asyncio.run(self.is_token_blacklisted(token))
            if is_blacklisted:
                logger.warning("Blacklisted token rejected")
                return None
        except Exception as e:
            logger.error(f"Blacklist check error: {e}")
            # Continue verification (fail-open for availability)

        # Existing JWT verification
        try:
            token_data = verify_jwt_token(token, token_type)
            # ... rest of verification ...
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
```

### Update Logout Endpoint

**File:** `backend-hormonia/app/api/v1/auth.py`

```python
@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(get_service_provider)
):
    """
    Logout user and blacklist current token.
    """
    token = credentials.credentials

    # Decode to get expiration
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        exp_timestamp = payload.get("exp")
    except:
        exp_timestamp = None

    # Blacklist token
    await services.auth_service.blacklist_token(
        token,
        exp_timestamp=exp_timestamp,
        reason="user_logout"
    )

    return {"message": "Logged out successfully"}
```

---

## Fix 3: Session Fingerprinting (SEC-003)

**Severity:** HIGH
**Effort:** 3 days
**Files:** New file + `auth_dependencies.py`

### Step 1: Create Fingerprint Service

**File:** `backend-hormonia/app/services/session_fingerprint.py`

```python
"""Session Fingerprinting - Detect session hijacking attempts"""
import hashlib
import logging
from typing import Optional
from fastapi import Request
import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)


class SessionFingerprint:
    """
    Generate and validate session fingerprints to detect hijacking.

    Fingerprint includes:
    - Client IP address
    - User-Agent string
    - User ID

    Stored in Redis with token hash as key.
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.strictness = getattr(settings, 'SESSION_FINGERPRINT_STRICTNESS', 'medium')
        # Strictness levels:
        # - strict: Block on any change (IP or User-Agent)
        # - medium: Allow IP change but not User-Agent (default)
        # - loose: Alert only, don't block

    def generate(self, request: Request, user_id: str) -> str:
        """
        Generate session fingerprint from request.

        Args:
            request: FastAPI Request object
            user_id: Authenticated user ID

        Returns:
            Fingerprint hash (SHA-256)
        """
        components = [
            self._get_client_ip(request),
            request.headers.get("user-agent", "unknown"),
            str(user_id)
        ]

        fingerprint_str = "|".join(components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP (handle proxies)"""
        # Check X-Forwarded-For header
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client
        return request.client.host if request.client else "unknown"

    async def store(self, token: str, fingerprint: str, ttl: int = 1800) -> None:
        """
        Store fingerprint for token.

        Args:
            token: JWT token (will be hashed)
            fingerprint: Session fingerprint hash
            ttl: Time-to-live in seconds (default: 30 min)
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        await self.redis.setex(
            f"fingerprint:token:{token_hash}",
            ttl,
            fingerprint
        )

        logger.debug(f"Stored session fingerprint (TTL: {ttl}s)")

    async def validate(
        self,
        token: str,
        request: Request,
        user_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate current request against stored fingerprint.

        Args:
            token: JWT token
            request: Current request
            user_id: Authenticated user ID

        Returns:
            (is_valid, reason) tuple
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        # Get stored fingerprint
        stored_fp = await self.redis.get(f"fingerprint:token:{token_hash}")
        if not stored_fp:
            # No fingerprint stored (first request or expired)
            logger.warning("No fingerprint found - storing new one")
            current_fp = self.generate(request, user_id)
            await self.store(token, current_fp)
            return True, None

        # Generate current fingerprint
        current_fp = self.generate(request, user_id)

        # Compare
        if stored_fp == current_fp:
            return True, None  # Match - valid

        # Mismatch detected
        reason = await self._analyze_mismatch(request, user_id, stored_fp, current_fp)

        # Apply strictness policy
        if self.strictness == "strict":
            return False, reason
        elif self.strictness == "medium":
            # Allow IP change but not User-Agent
            stored_parts = self._parse_fingerprint(stored_fp)
            current_parts = self._parse_fingerprint(current_fp)

            if stored_parts["user_agent"] != current_parts["user_agent"]:
                return False, "User-Agent changed (potential hijacking)"
            else:
                logger.warning(f"IP changed but User-Agent same: {reason}")
                return True, reason  # Allow but log
        else:  # loose
            logger.warning(f"Fingerprint mismatch (loose mode): {reason}")
            return True, reason  # Allow but alert

    async def _analyze_mismatch(
        self,
        request: Request,
        user_id: str,
        stored_fp: str,
        current_fp: str
    ) -> str:
        """Analyze what changed between fingerprints"""
        # This is simplified - in production, decrypt and compare components
        return "Session fingerprint mismatch detected"

    def _parse_fingerprint(self, fp: str) -> dict:
        """Parse fingerprint (if stored unencrypted) - placeholder"""
        # In production, store components separately for analysis
        return {"user_agent": "unknown"}

    async def clear(self, token: str) -> None:
        """Clear fingerprint for token (on logout)"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        await self.redis.delete(f"fingerprint:token:{token_hash}")
        logger.debug("Cleared session fingerprint")
```

### Step 2: Integrate into Authentication

**File:** `backend-hormonia/app/dependencies/auth_dependencies.py`

```python
from app.services.session_fingerprint import SessionFingerprint

async def get_current_user(
    request: Request,  # ADD Request parameter
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(_get_service_provider)
) -> User:
    """
    Get current user with session fingerprinting.
    """
    # ... existing Firebase verification ...

    # NEW: Session fingerprinting check
    if services.redis:
        fingerprint_service = SessionFingerprint(services.redis)

        is_valid, reason = await fingerprint_service.validate(
            token=credentials.credentials,
            request=request,
            user_id=str(user.id)
        )

        if not is_valid:
            logger.error(
                f"Session hijacking detected: {reason}",
                extra={
                    "user_id": user.id,
                    "ip": request.client.host,
                    "user_agent": request.headers.get("user-agent")
                }
            )

            # Alert security team
            await _alert_security_team(user, reason, request)

            # Blacklist token
            await services.auth_service.blacklist_token(
                credentials.credentials,
                reason="session_hijacking_detected"
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalid - please re-authenticate",
                headers={"WWW-Authenticate": "Bearer"}
            )

    return user


async def _alert_security_team(user: User, reason: str, request: Request):
    """Send security alert (implement based on your alerting system)"""
    logger.critical(
        f"SECURITY ALERT: Possible session hijacking",
        extra={
            "event_type": "session_hijacking",
            "user_id": user.id,
            "email": user.email,
            "reason": reason,
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    # TODO: Integrate with alerting system (PagerDuty, Slack, etc.)
```

---

## Fix 4: Fail-Secure Rate Limiting (SEC-004)

**Severity:** HIGH
**Effort:** 0.5 days
**Files:** `auth.py`, `enhanced_middleware.py`

### Implementation

**File:** `backend-hormonia/app/services/auth.py`

```python
async def _is_rate_limited(self, email: str, client_ip: Optional[str] = None) -> bool:
    """
    FAIL-SECURE rate limiting: Block requests when Redis unavailable.
    """
    # CRITICAL CHANGE: Require Redis in production
    if settings.ENVIRONMENT == "production" and not (self.redis and await self._redis_is_connected()):
        logger.error(
            "Rate limiting unavailable in PRODUCTION - blocking request (fail-secure)",
            extra={
                "event_type": "rate_limit_unavailable",
                "email": email,
                "ip": client_ip
            }
        )

        # FAIL SECURE: Block request
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable - please try again later"
        )

    # Development: Allow fallback
    if not (self.redis and await self._redis_is_connected()):
        logger.warning("Rate limiting unavailable (development) - allowing request")
        return False

    # Normal Redis-based check
    return await self._is_rate_limited_redis(email, client_ip)
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Generate `REDIS_ENCRYPTION_KEY` and add to `.env`
- [ ] Run database migrations (if schema changes)
- [ ] Update `requirements.txt`: `cryptography==41.0.7`
- [ ] Configure `SESSION_FINGERPRINT_STRICTNESS` (recommend: `medium`)
- [ ] Set up security alerting (Slack/PagerDuty webhook)

### Testing

- [ ] Unit tests for encryption/decryption
- [ ] Integration test: Login → Logout (token blacklist)
- [ ] Security test: Session hijacking simulation
- [ ] Load test: Rate limiting under Redis failure
- [ ] Verify HIPAA compliance (encrypted Redis storage)

### Monitoring

- [ ] Alert on encryption errors
- [ ] Alert on session hijacking detection
- [ ] Alert on Redis unavailability (rate limiting bypass)
- [ ] Dashboard: Active sessions, blacklisted tokens

### Rollback Plan

1. Disable encryption: `REDIS_ENABLE_ENCRYPTION=false`
2. Revert to previous auth.py version
3. Clear Redis: `redis-cli FLUSHDB` (lose sessions)
4. Restart services

---

**Estimated Total Effort:** 6.5 days
**Blocking Production:** YES (HIPAA compliance requires encryption)
**Security Audit Required:** After implementation
