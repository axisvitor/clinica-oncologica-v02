# Supabase References Removal Fix

## Issue
The RLS middleware was trying to access `settings.SUPABASE_JWT_HEADER_NAME` which doesn't exist, causing authentication errors:
```
Error extracting JWT token: 'Settings' object has no attribute 'SUPABASE_JWT_HEADER_NAME'
```

## Root Cause
The system migrated from Supabase to Firebase authentication, but some middleware code still contained obsolete Supabase references that were never removed.

## Problem Code
```python
# OLD (Supabase-based)
auth_header = request.headers.get(settings.SUPABASE_JWT_HEADER_NAME)
if auth_header.startswith(f"{settings.SUPABASE_JWT_PREFIX} "):
    return auth_header[len(f"{settings.SUPABASE_JWT_PREFIX} "):].strip()

# Also tried obsolete cookie
token = request.cookies.get("supabase_auth_token")
```

## Solution Applied
Updated the JWT token extraction in `app/middleware/rls_middleware.py` to use standard Firebase/Bearer authentication:

```python
# NEW (Firebase/Bearer-based)
auth_header = request.headers.get("Authorization")
if auth_header.startswith("Bearer "):
    return auth_header[7:].strip()  # Remove "Bearer " prefix

# Updated cookie name
token = request.cookies.get("auth_token")
```

## Changes Made
1. **Authorization Header**: Changed from `settings.SUPABASE_JWT_HEADER_NAME` to standard `"Authorization"`
2. **Token Prefix**: Changed from `settings.SUPABASE_JWT_PREFIX` to standard `"Bearer "`
3. **Cookie Name**: Changed from `"supabase_auth_token"` to `"auth_token"`
4. **Removed Dependencies**: Eliminated need for Supabase-specific configuration

## Files Modified
- `backend-hormonia/app/middleware/rls_middleware.py` - Updated `get_jwt_token()` function

## Current Authentication Flow
The system now properly uses:
1. **Firebase Authentication**: For user verification and token generation
2. **Standard Bearer Tokens**: `Authorization: Bearer <firebase-token>`
3. **WebSocket Token Parameter**: `?token=<firebase-token>` for WebSocket connections
4. **Session Cookies**: `auth_token` cookie for session-based authentication

## Verification
After applying the fix:
- ✅ No more "SUPABASE_JWT_HEADER_NAME" errors in logs
- ✅ Endpoints return proper 401 (Unauthorized) instead of 500 (Server Error)
- ✅ Authentication middleware works with Firebase tokens
- ✅ WebSocket connections authenticate properly

## Testing
Use the test script to verify the fix:
```bash
python sql/test_auth_fix.py
```

Expected results:
- `/api/v2/patients` → 401 (authentication required)
- `/api/v2/auth/me` → 401 (authentication required)  
- `/api/v2/csrf-token` → 200 (public endpoint)

## Impact
- ✅ Eliminates server errors during authentication
- ✅ Enables proper Firebase token handling
- ✅ Fixes patients page authentication flow
- ✅ Removes obsolete Supabase dependencies

## Security Note
This change maintains the same security level while using the correct authentication system (Firebase instead of Supabase).