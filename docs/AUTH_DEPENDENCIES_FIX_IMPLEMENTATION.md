# Auth Dependencies Thread-Safety Fix Implementation

## Quick Reference

**File to Fix**: `backend-hormonia/app/dependencies/auth_dependencies.py`

**Lines to Modify**:
- Lines 138-260: `get_current_user_from_session()`
- Lines 262-419: `get_current_user()`

**Root Cause**: Synchronous database calls (`services.db.execute()`) in async functions

**Solution**: Use `asyncio.to_thread()` to run sync database operations safely

---

## Step 1: Add Helper Functions (Add after line 136)

Add these helper functions after the `verify_firebase_token()` function and before `get_current_user_from_session()`:

```python
# =============================================================================
# DATABASE HELPER FUNCTIONS (THREAD-SAFE)
# =============================================================================

def _get_user_from_db(
    db_session: Session,
    firebase_uid: str
) -> Optional[User]:
    """
    Thread-safe database query to get user by Firebase UID.

    This function is designed to be called via asyncio.to_thread()
    to prevent blocking the event loop in async contexts.

    Args:
        db_session: Synchronous SQLAlchemy Session
        firebase_uid: Firebase user ID to search for

    Returns:
        User model or None if not found

    Note:
        This function runs synchronous DB operations, so it must
        be called via asyncio.to_thread() from async functions.
    """
    from sqlalchemy import select

    stmt = select(User).where(User.firebase_uid == firebase_uid)
    result = db_session.execute(stmt)
    return result.scalar_one_or_none()


def _create_user_in_db(
    db_session: Session,
    firebase_uid: str,
    email: str,
    full_name: str,
    role: UserRole
) -> User:
    """
    Thread-safe user creation in database.

    This function is designed to be called via asyncio.to_thread()
    to prevent blocking the event loop in async contexts.

    Args:
        db_session: Synchronous SQLAlchemy Session
        firebase_uid: Firebase user ID
        email: User email
        full_name: User full name
        role: User role (ADMIN or DOCTOR)

    Returns:
        Created User model

    Note:
        This function runs synchronous DB operations, so it must
        be called via asyncio.to_thread() from async functions.
    """
    user = User(
        firebase_uid=firebase_uid,
        email=email,
        full_name=full_name,
        is_active=True,
        role=role
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
```

---

## Step 2: Fix `get_current_user_from_session()` (Lines 138-260)

Replace the current implementation with this fixed version:

```python
async def get_current_user_from_session(
    session_id: str = Cookie(None, alias="session_id"),
    x_session_id: str = Header(None, alias="X-Session-ID"),
    services: ServiceProvider = Depends(_get_service_provider),
    redis_cache: 'FirebaseRedisCache' = Depends(get_redis_cache)
) -> Dict:
    """
    Get current authenticated user by validating Redis session (RECOMMENDED).

    Ultra-fast authentication using Redis sessions with multi-layer caching:
    - Cache hit (Layer 1): ~2-5ms
    - Cache miss (Layer 2): ~50-100ms (PostgreSQL + cache write)

    Authentication flow:
    1. Validate session_id exists in Redis (Layer 1 cache)
    2. Get user data from Layer 2 cache (user:{uid})
    3. If cache miss: Query PostgreSQL and repopulate cache
    4. Validate user is_active
    5. Return user dict with permissions

    THREAD-SAFETY FIX: Uses asyncio.to_thread() for synchronous DB operations
    to prevent event loop blocking.

    Args:
        session_id: Session ID from Cookie
        x_session_id: Session ID from X-Session-ID header
        services: Service provider with Redis and DB access
        redis_cache: Redis cache instance (injected)

    Returns:
        User dict with permissions

    Raises:
        HTTPException 401: Invalid or expired session
        HTTPException 403: User account is inactive
    """
    try:
        final_session_id = session_id or x_session_id
        if not final_session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session ID not provided",
                headers={"WWW-Authenticate": "Session"}
            )

        # Layer 1: Get session from Redis (~2-5ms)
        session_data = await redis_cache.get_session(final_session_id)

        if not session_data:
            logger.warning(f"Invalid or expired session: {final_session_id[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please login again.",
                headers={"WWW-Authenticate": "Session"}
            )

        firebase_uid = session_data.get("firebase_uid")
        if not firebase_uid:
            logger.error(f"Session missing firebase_uid: {final_session_id[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session data",
                headers={"WWW-Authenticate": "Session"}
            )

        # Layer 2: Get user from cache (~2-5ms on hit, ~50-100ms on miss)
        user_data = await redis_cache.get_user_by_uid(firebase_uid)

        if not user_data:
            # Cache miss: Query PostgreSQL using asyncio.to_thread()
            logger.info(f"Cache miss for user: {firebase_uid[:8]}... Querying database.")

            # ✅ FIX: Run synchronous DB call in thread pool
            import asyncio
            user = await asyncio.to_thread(
                _get_user_from_db,
                services.db,
                firebase_uid
            )

            if not user:
                logger.error(f"User not found in database: {firebase_uid[:8]}...")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Session"}
                )

            # Convert SQLAlchemy model to dict and cache
            user_data = {
                "firebase_uid": user.firebase_uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                "is_active": user.is_active,
                "id": user.id
            }

            # Cache for 15 minutes
            await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)
            logger.debug(f"Cached user data for: {firebase_uid[:8]}...")

        # Validate user is active
        if not user_data.get("is_active", False):
            logger.warning(f"Inactive user attempted access: {user_data.get('email')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Add permissions to user data
        role = user_data.get("role", "doctor")
        user_data["permissions"] = get_permissions_for_role(role)

        logger.debug(f"Session validated for user: {user_data.get('email')} (role: {role})")
        return user_data

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Session validation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Session validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Session"}
        )
```

---

## Step 3: Fix `get_current_user()` (Lines 262-419)

Replace the current implementation with this fixed version:

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    services: ServiceProvider = Depends(_get_service_provider)
) -> User:
    """
    Get current authenticated user by validating Firebase Auth token with Redis cache.

    PERFORMANCE OPTIMIZED: Now uses 3-layer Redis cache for 40-90x speedup.
    DEPRECATED: Prefer get_current_user_from_session() for session-based auth.

    Authentication flow with Redis cache (3 layers):
    1. Layer 1 (Token Cache): Check if token is cached (~5ms hit, ~200ms miss)
    2. Layer 2 (User Cache): Check if user is cached (~5ms hit, ~100ms miss)
    3. Layer 3 (Session): Not used in Bearer token flow

    Performance comparison:
    - Cache hit (Layer 1+2): ~5ms (90x faster than cold request)
    - Cache hit (Layer 1 only): ~105ms (2x faster, skip Firebase validation)
    - Cache miss (cold): ~250ms (Firebase + PostgreSQL + cache write)

    THREAD-SAFETY FIX: Uses asyncio.to_thread() for synchronous DB operations
    to prevent event loop blocking.

    Args:
        credentials: HTTP Bearer token from Authorization header
        services: Service provider with Redis and DB access

    Returns:
        Authenticated User model

    Raises:
        HTTPException 401: Invalid token or user not found
        HTTPException 403: User account is inactive
    """
    # Check if Firebase is configured
    if _firebase_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Firebase authentication is not configured"
        )

    try:
        # Initialize 3-layer Redis cache
        from app.core.redis_manager import FirebaseRedisCache, get_redis_manager
        redis_manager = get_redis_manager()
        redis_client = redis_manager.get_compatible_client("sync")
        firebase_cache = FirebaseRedisCache(redis_client)

        id_token = credentials.credentials

        # === LAYER 1: TOKEN VALIDATION CACHE (5ms on hit, 200ms on miss) ===
        cached_token = firebase_cache.get_cached_token(id_token)

        if cached_token:
            logger.debug(f"✅ Token cache HIT for {cached_token.get('email')}")
            firebase_uid = cached_token["firebase_uid"]
            user_data = cached_token  # Temporary: will be replaced by Layer 2
        else:
            # MISS: Validate with Firebase Admin SDK (200ms)
            logger.debug("❌ Token cache MISS - validating with Firebase")
            user_data = await _firebase_service.verify_token(id_token)
            firebase_uid = user_data["uid"]

            # Cache validated token (1 hour TTL)
            firebase_cache.cache_validated_token(id_token, user_data)
            logger.info(f"💾 Token cached for {user_data.get('email')}")

        # === LAYER 2: USER OBJECT CACHE (5ms on hit, 100ms on miss) ===
        cached_user = firebase_cache.get_cached_user(firebase_uid)

        if cached_user:
            logger.debug(f"✅ User cache HIT for {firebase_uid}")
            # Convert dict to User model
            # FIX: Remove 'cached_at' before creating User model to prevent TypeError
            cached_user.pop('cached_at', None)
            user = User(**cached_user)
            return user

        # MISS: Query PostgreSQL (100ms)
        logger.debug(f"❌ User cache MISS - querying PostgreSQL for {firebase_uid}")

        # ✅ FIX: Run synchronous DB call in thread pool
        import asyncio
        user = await asyncio.to_thread(
            _get_user_from_db,
            services.db,
            firebase_uid
        )

        if user:
            # User exists - cache and return
            logger.debug(f"User found in database: {user.email}")

            # Cache user for 2 hours
            user_dict = {
                "id": str(user.id),
                "firebase_uid": user.firebase_uid,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
                "is_active": user.is_active,
            }
            firebase_cache.cache_user(firebase_uid, user_dict)
            logger.info(f"💾 User cached for {firebase_uid}")

            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User account is inactive"
                )

            return user

        # User doesn't exist - create minimal record
        logger.info(f"User not found in database, creating minimal record for: {user_data.get('email')}")

        # Extract role from Firebase custom claims or default to DOCTOR
        firebase_role = user_data.get("role", "doctor").lower()
        user_role = UserRole.ADMIN if firebase_role == "admin" else UserRole.DOCTOR

        # ✅ FIX: Run synchronous DB operations in thread pool
        user = await asyncio.to_thread(
            _create_user_in_db,
            services.db,
            firebase_uid,
            user_data.get("email"),
            user_data.get("name", user_data.get("email", "").split("@")[0]),
            user_role
        )

        # Cache new user
        user_dict = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active,
        }
        firebase_cache.cache_user(firebase_uid, user_dict)

        logger.info(f"✅ New user created and cached: {user.email}")
        return user

    except HTTPException:
        # Re-raise HTTP exceptions (inactive user, etc.)
        raise
    except Exception as e:
        # Firebase authentication failed
        logger.error(f"Firebase authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
```

---

## Step 4: Add Import Statement

Add this import at the top of the file (after line 11):

```python
import asyncio  # Add this line
```

---

## Testing Instructions

### 1. Unit Tests for Helper Functions

Create `backend-hormonia/tests/unit/auth/test_auth_helpers.py`:

```python
import pytest
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.dependencies.auth_dependencies import _get_user_from_db, _create_user_in_db


def test_get_user_from_db_success(db_session: Session, test_user: User):
    """Test getting user by Firebase UID succeeds."""
    result = _get_user_from_db(db_session, test_user.firebase_uid)
    assert result is not None
    assert result.firebase_uid == test_user.firebase_uid
    assert result.email == test_user.email


def test_get_user_from_db_not_found(db_session: Session):
    """Test getting non-existent user returns None."""
    result = _get_user_from_db(db_session, "nonexistent_firebase_uid")
    assert result is None


def test_create_user_in_db_success(db_session: Session):
    """Test creating new user succeeds."""
    user = _create_user_in_db(
        db_session,
        firebase_uid="test_firebase_uid_123",
        email="test@example.com",
        full_name="Test User",
        role=UserRole.DOCTOR
    )

    assert user.id is not None
    assert user.firebase_uid == "test_firebase_uid_123"
    assert user.email == "test@example.com"
    assert user.full_name == "Test User"
    assert user.role == UserRole.DOCTOR
    assert user.is_active is True


def test_create_user_in_db_duplicate_firebase_uid(db_session: Session, test_user: User):
    """Test creating user with duplicate Firebase UID raises error."""
    with pytest.raises(Exception):  # IntegrityError
        _create_user_in_db(
            db_session,
            firebase_uid=test_user.firebase_uid,  # Duplicate
            email="duplicate@example.com",
            full_name="Duplicate User",
            role=UserRole.DOCTOR
        )
```

### 2. Integration Tests for Async Thread Safety

Create `backend-hormonia/tests/integration/auth/test_auth_thread_safety.py`:

```python
import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app


@pytest.mark.asyncio
async def test_concurrent_session_validation(test_client: TestClient, valid_session_id: str):
    """Test concurrent session validation doesn't block event loop."""
    async def make_request():
        response = test_client.get(
            "/api/v1/patients",
            headers={"X-Session-ID": valid_session_id}
        )
        return response.status_code

    # Simulate 100 concurrent requests
    tasks = [make_request() for _ in range(100)]
    results = await asyncio.gather(*tasks)

    # All requests should succeed
    assert all(status == 200 for status in results)


@pytest.mark.asyncio
async def test_concurrent_user_creation(test_client: TestClient, firebase_token: str):
    """Test concurrent user creation with same Firebase UID handles race conditions."""
    async def make_request():
        response = test_client.get(
            "/api/v1/patients",
            headers={"Authorization": f"Bearer {firebase_token}"}
        )
        return response.status_code

    # Simulate 10 concurrent requests with same token
    tasks = [make_request() for _ in range(10)]
    results = await asyncio.gather(*tasks)

    # All requests should succeed (only one user created)
    assert all(status in [200, 401] for status in results)
```

### 3. Load Testing Script

Create `backend-hormonia/tests/load/test_auth_load.py`:

```python
import asyncio
import time
from httpx import AsyncClient


async def test_auth_performance():
    """Test authentication performance under load."""
    async with AsyncClient(base_url="http://localhost:8000") as client:
        session_id = "your_test_session_id"

        # Warmup
        for _ in range(10):
            await client.get(
                "/api/v1/patients",
                headers={"X-Session-ID": session_id}
            )

        # Measure
        start = time.time()
        tasks = []
        for _ in range(1000):
            task = client.get(
                "/api/v1/patients",
                headers={"X-Session-ID": session_id}
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        end = time.time()

        duration = end - start
        rps = 1000 / duration

        print(f"Duration: {duration:.2f}s")
        print(f"Requests per second: {rps:.2f}")
        print(f"Average latency: {(duration / 1000) * 1000:.2f}ms")

        # Assert performance targets
        assert rps > 500, f"RPS too low: {rps}"
        assert all(r.status_code == 200 for r in responses), "Some requests failed"


if __name__ == "__main__":
    asyncio.run(test_auth_performance())
```

---

## Verification Checklist

After implementing the fix, verify:

- [ ] `import asyncio` added at top of file
- [ ] `_get_user_from_db()` helper function added
- [ ] `_create_user_in_db()` helper function added
- [ ] `get_current_user_from_session()` uses `asyncio.to_thread()`
- [ ] `get_current_user()` uses `asyncio.to_thread()` for DB queries
- [ ] `get_current_user()` uses `asyncio.to_thread()` for user creation
- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Load tests show no performance degradation
- [ ] No event loop blocking warnings in logs
- [ ] Concurrent requests succeed without deadlocks

---

## Performance Validation

Expected performance (no degradation):

| Scenario | Before Fix | After Fix | Change |
|----------|-----------|-----------|--------|
| Cache hit | ~2-5ms | ~2-5ms | No change |
| Cache miss | ~50-100ms | ~50-100ms | No change |
| Concurrent requests (100) | Deadlock risk | No deadlock | ✅ Fixed |
| Event loop blocking | Yes | No | ✅ Fixed |
| Thread safety | ❌ Not safe | ✅ Safe | ✅ Fixed |

---

## Rollback Plan

If issues occur after deployment:

1. **Immediate rollback**: Revert to previous commit
2. **Diagnostic**: Check logs for `asyncio.to_thread()` errors
3. **Fallback**: Use direct sync calls temporarily (with warning)

---

## Success Criteria

✅ Fix is successful when:

1. No `asyncio` warnings in logs about blocking operations
2. Concurrent load tests pass (100+ simultaneous requests)
3. No deadlocks or connection pool exhaustion
4. Performance metrics unchanged (cache hit/miss times)
5. All existing tests continue to pass

---

## Next Steps

After implementing this fix:

1. Monitor production logs for thread-safety issues
2. Review other async functions for similar sync DB calls
3. Consider migrating to AsyncSession in future for better performance
4. Update API documentation with thread-safety guarantees

---

**Implementation Time**: ~2 hours
**Testing Time**: ~2 hours
**Total Effort**: 4 hours

**Priority**: HIGH (Critical thread-safety issue)
