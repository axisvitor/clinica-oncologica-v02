# API Contract Analysis: Authentication Endpoints

## Executive Summary

**Status**: ⚠️ **PARTIAL MISMATCH** - Authentication disabled, response handling issues detected
**Critical Issues**: 3 High Priority
**Recommendations**: Align error handling, update frontend to match Firebase-only auth

---

## Backend Authentication API (Pydantic Models)

### `/api/v1/auth/login` - **DEPRECATED (HTTP 410)**
- **Status**: Disabled - Returns HTTP 410 Gone
- **Backend Response**: `{ "detail": "Local login is disabled: Firebase-only authentication" }`
- **Frontend Expectation**: LoginResponse with tokens
- **Issue**: Frontend still expects local auth, should use Supabase/Firebase client-side

### `/api/v1/auth/login-json` - **DEPRECATED (HTTP 410)**
- **Request Schema** (backend): `LoginRequest`
  ```python
  class LoginRequest(BaseModel):
      email: EmailStr
      password: str
  ```
- **Response**: HTTP 410 with error message
- **Frontend Contract**: Expects `LoginResponse`
- **Issue**: ❌ Frontend not updated to handle 410 status

### `/api/v1/auth/refresh` - **DEPRECATED (HTTP 410)**
- **Request Schema**: `RefreshTokenRequest { refresh_token: str }`
- **Response**: HTTP 410 with error message
- **Frontend**: Expects token refresh
- **Issue**: ❌ Should be handled client-side by Firebase

### `/api/v1/auth/me` - ✅ **ACTIVE**
- **Backend Response** (`UserResponse`):
  ```python
  {
      id: UUID,
      email: str,
      full_name: Optional[str],
      role: str,
      is_active: bool
  }
  ```
- **Frontend Type** (`AuthMeResponse`):
  ```typescript
  {
      id: string,
      email: string,
      full_name: string,
      role: string,
      is_active: boolean
  }
  ```
- **Status**: ✅ **MATCH** - Types align correctly
- **Note**: Frontend transforms to add `permissions: []` and `created_at`

### `/api/v1/auth/logout` - ✅ **ACTIVE**
- **Backend Response**: `{ "message": "Successfully logged out" }`
- **Frontend Type** (`LogoutResponse`):
  ```typescript
  { message: string }
  ```
- **Status**: ✅ **MATCH**

### `/api/v1/auth/notifications` - ✅ **IMPLEMENTED**
- **Backend Response**:
  ```python
  {
      notifications: List[NotificationResponse],
      total: int,
      unread_count: int
  }
  ```
- **Frontend Expects**: Same structure
- **Status**: ✅ **MATCH**

---

## User Preferences Endpoints

### `/api/v1/auth/users/preferences` (GET/PUT/PATCH)
- **Backend Schema** (`UserPreferences`):
  ```python
  {
      notification_email: bool = True,
      notification_sms: bool = True,
      notification_whatsapp: bool = True,
      language: str = "pt-BR",
      timezone: str = "America/Sao_Paulo",
      theme: str = "light",
      dashboard_widgets: Optional[Dict],
      email_digest_frequency: str = "daily",
      data_sharing_consent: bool = True,
      marketing_consent: bool = False
  }
  ```
- **Frontend**: Not explicitly typed in api-responses.ts
- **Issue**: ⚠️ Missing TypeScript interface for preferences

### `/api/v1/auth/profile` (PUT) - Profile Update
- **Backend Request** (`ProfileUpdateRequest`):
  ```python
  {
      full_name: Optional[str],
      email: Optional[str],
      phone: Optional[str],
      specialty: Optional[str]
  }
  ```
- **Backend Response** (`ProfileUpdateResponse`):
  ```python
  {
      id: str,
      email: str,
      full_name: str,
      phone: Optional[str],
      specialty: Optional[str],
      updated_at: datetime
  }
  ```
- **Frontend**: Not typed in api-responses.ts
- **Issue**: ⚠️ Missing TypeScript types

### `/api/v1/auth/avatar` (POST) - Avatar Upload
- **Backend**: Accepts `multipart/form-data`
- **Response**:
  ```python
  {
      success: bool,
      avatar_url: str,
      message: str
  }
  ```
- **Frontend**: Not implemented in api-client.ts
- **Issue**: ⚠️ Missing frontend implementation

### `/api/v1/auth/password` (PUT) - Password Change
- **Backend Request** (`PasswordChangeRequest`):
  ```python
  { new_password: str }
  ```
- **Backend Response**: `SuccessResponse`
- **Frontend**: Not implemented
- **Issue**: ⚠️ Missing frontend implementation

---

## Error Response Contract Analysis

### Backend Error Schemas (common.py)

**Standard Error Responses:**
1. `ErrorResponse` - Generic errors
   ```python
   {
       error: str,
       message: str,
       details: Optional[dict],
       timestamp: datetime
   }
   ```

2. `ValidationErrorResponse` - Validation failures
   ```python
   {
       error: "validation_error",
       message: str,
       field_errors: dict[str, list[str]],
       timestamp: datetime
   }
   ```

3. `UnauthorizedErrorResponse` - 401 errors
   ```python
   {
       error: "unauthorized",
       message: "Authentication required",
       timestamp: datetime
   }
   ```

4. `ForbiddenErrorResponse` - 403 errors
   ```python
   {
       error: "forbidden",
       message: "Insufficient permissions",
       required_permissions: Optional[list[str]],
       timestamp: datetime
   }
   ```

5. `RateLimitErrorResponse` - 429 errors
   ```python
   {
       error: "rate_limit_exceeded",
       message: str,
       retry_after: int,
       limit: int,
       timestamp: datetime
   }
   ```

### Frontend Error Handling (auth-error-handler.ts)

**Error Types Detected:**
```typescript
enum AuthErrorType {
    AUTHENTICATION_REQUIRED,
    INVALID_CREDENTIALS,
    SESSION_EXPIRED,
    INSUFFICIENT_PERMISSIONS,
    RLS_VIOLATION,
    NETWORK_ERROR,
    RATE_LIMITED,
    SERVER_ERROR,
    UNKNOWN_ERROR
}
```

**Error Pattern Matching:**
- ✅ RLS violations detected correctly
- ✅ 401/403 status codes handled
- ✅ Rate limiting (429) handled
- ✅ Network errors handled
- ⚠️ Backend error response structure not validated

---

## HTTP Status Code Mapping

### Backend Implementation (auth.py)
- **410 Gone**: Login/refresh deprecated
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Insufficient permissions
- **400 Bad Request**: Validation errors
- **429 Too Many Requests**: Rate limiting
- **500 Internal Server Error**: Server errors

### Frontend Handling (api-client.ts)
- ✅ **401**: Handled by auth-error-handler
- ✅ **403**: Detected as RLS_VIOLATION
- ✅ **429**: Rate limit detection
- ❌ **410**: Not explicitly handled (deprecated endpoints)
- ⚠️ **Error response structure**: Uses generic `ApiError` class

---

## Critical Issues Summary

### 🔴 HIGH PRIORITY

1. **Deprecated Auth Endpoints Not Handled**
   - **Issue**: Frontend still references login/refresh endpoints
   - **Location**: `api-client.ts` lines 267-272
   - **Impact**: Throws HTTP 410 errors instead of redirecting to Firebase
   - **Fix**: Remove local auth methods, always use Supabase client

2. **Missing TypeScript Types for New Endpoints**
   - **Missing**:
     - `ProfileUpdateRequest`
     - `ProfileUpdateResponse`
     - `UserPreferences`
     - `PasswordChangeRequest`
     - `NotificationResponse`
   - **Location**: `api-responses.ts` needs additions
   - **Impact**: No type safety for settings/profile features

3. **Error Response Structure Mismatch**
   - **Backend**: Returns structured error objects with `error`, `message`, `timestamp`
   - **Frontend**: Expects generic `{ message: string }` or `{ detail: string }`
   - **Impact**: Error messages may not display correctly
   - **Fix**: Standardize error handling to match backend schemas

### ⚠️ MEDIUM PRIORITY

4. **Avatar Upload Not Implemented**
   - Backend endpoint exists at `/api/v1/auth/avatar`
   - Frontend has no corresponding implementation
   - Should use FormData for file uploads

5. **Password Change Not Implemented**
   - Backend supports password change via Firebase Admin
   - Frontend missing implementation

6. **Preferences Management Incomplete**
   - Backend fully implements preferences CRUD
   - Frontend lacks typed interfaces

---

## Recommendations

### Immediate Actions

1. **Remove Deprecated Auth Methods**
   ```typescript
   // REMOVE from api-client.ts
   auth = {
       login: async () => { throw new ApiError(410, ...) },
       refresh: async () => { throw new ApiError(410, ...) }
   }
   ```

2. **Add Missing TypeScript Interfaces**
   ```typescript
   // Add to api-responses.ts
   export interface ProfileUpdateRequest { ... }
   export interface UserPreferences { ... }
   export interface NotificationResponse { ... }
   ```

3. **Standardize Error Responses**
   - Update ApiError class to match backend error schemas
   - Add proper typing for error.data structure

4. **Implement Missing Features**
   - Avatar upload endpoint
   - Password change functionality
   - Preferences management UI

### Long-term Improvements

1. Generate TypeScript types from Pydantic schemas automatically
2. Add runtime validation using Zod or similar
3. Implement comprehensive error type guards
4. Add error code constants shared between frontend/backend

---

## Testing Checklist

- [ ] Test authentication with Firebase only (no local login)
- [ ] Verify `/auth/me` returns correct user data
- [ ] Test logout clears session properly
- [ ] Verify 410 errors don't break the app
- [ ] Test error messages display correctly
- [ ] Validate all error types are caught and displayed
- [ ] Test rate limiting shows correct messages
- [ ] Verify RLS violations show permission denied messages

---

**Generated**: 2025-10-04
**Analyst**: Claude Code Quality Analyzer
**Next Review**: After implementing recommendations
