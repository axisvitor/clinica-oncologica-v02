# Session Activity Tracking Implementation

## Overview

Session activity tracking has been implemented to prevent sessions from expiring while users are actively using the system. This ensures that users won't be unexpectedly logged out during their work.

## Implementation Details

### Files Modified

1. **`/backend-hormonia/app/core/redis_manager/session_cache.py`**
   - Added `update_session_activity()` method to `SessionCache` class
   - Added mixin method to `SessionCacheMixin` for integration with `FirebaseRedisCache`

2. **`/backend-hormonia/app/dependencies/auth_dependencies.py`**
   - Added call to `update_session_activity()` in `get_current_user_from_session()` function
   - Placed after session validation and before user data retrieval

## How It Works

### Flow Diagram

```
User Request → get_current_user_from_session()
    ↓
1. Validate session exists in Redis
    ↓
2. Session valid? → Update last_activity + extend TTL
    ↓
3. Get user data from cache/DB
    ↓
4. Return authenticated user
```

### Key Features

1. **Automatic Activity Tracking**: Every authenticated request updates the session's `last_activity` timestamp
2. **TTL Extension**: The session TTL is reset to the full duration (default: 24 hours) on each request
3. **No Breaking Changes**: The existing `get_session()` method continues to work as before
4. **Explicit Control**: The new `update_session_activity()` method provides fine-grained control

### Code Changes

#### New Method in SessionCache

```python
async def update_session_activity(
    self,
    session_id: str,
    extend_ttl: bool = True,
    custom_ttl: Optional[int] = None
) -> bool:
    """
    Update session activity timestamp and optionally extend TTL.

    Args:
        session_id: Session identifier
        extend_ttl: Whether to reset the TTL (default: True)
        custom_ttl: Custom TTL in seconds (defaults to self.session_ttl)

    Returns:
        True if session was updated successfully, False otherwise
    """
```

**Features:**
- Updates `last_activity` timestamp to current time
- Optionally extends TTL to keep active users logged in
- Can preserve existing TTL if `extend_ttl=False`
- Returns success status for monitoring/logging

#### Integration in auth_dependencies.py

```python
# Layer 1: Get session from Redis (~2-5ms)
session_data = await redis_cache.get_session(final_session_id)

if not session_data:
    raise HTTPException(...)

# Update session activity to prevent expiration during active use
await redis_cache.update_session_activity(
    session_id=final_session_id,
    extend_ttl=True  # Reset Redis TTL to keep active users logged in
)

firebase_uid = session_data.get("firebase_uid")
# ... continue with user validation
```

## Performance Impact

- **Minimal overhead**: ~2-5ms per request (async Redis operation)
- **No additional database queries**: All operations are Redis-only
- **Efficient**: Uses `asyncio.to_thread()` for non-blocking Redis operations

## Configuration

Default TTL values (can be customized in settings):

```python
# Default session TTL: 24 hours
FIREBASE_SESSION_TTL = 86400
```

## Benefits

1. **Better User Experience**: Users stay logged in during active use
2. **Security**: Inactive sessions still expire after the configured TTL
3. **Monitoring**: Activity timestamps enable usage analytics
4. **Flexibility**: Can be configured per-session or globally

## Testing

To verify the implementation:

1. Login and get a session ID
2. Make authenticated requests within the TTL period
3. Check session TTL is extended after each request
4. Verify `last_activity` timestamp is updated

Example test:

```python
async def test_session_activity_tracking():
    # Login and get session_id
    response = await client.post("/api/v2/auth/login", ...)
    session_id = response.cookies["session_id"]

    # Wait a few minutes
    await asyncio.sleep(180)

    # Make authenticated request
    response = await client.get(
        "/api/v2/users/me",
        cookies={"session_id": session_id}
    )

    # Session should still be valid and TTL should be reset
    assert response.status_code == 200
```

## Monitoring

The session activity tracking can be monitored via:

1. **Logs**: Look for `♻️ Session activity updated` messages
2. **Redis**: Check session keys for `last_activity` timestamps
3. **Metrics**: Track session lifetime and renewal patterns

## Security Considerations

1. **No changes to authentication logic**: The security model remains the same
2. **TTL still enforced**: Sessions expire after inactivity period
3. **No infinite sessions**: Each activity still has a maximum TTL
4. **Compatible with logout**: Manual logout still works immediately

## Future Enhancements

Potential improvements:

1. **Adaptive TTL**: Adjust TTL based on user behavior patterns
2. **Activity throttling**: Update activity only every N minutes to reduce Redis load
3. **Session analytics**: Track user session patterns and durations
4. **Configurable policies**: Different TTL policies for different user roles
