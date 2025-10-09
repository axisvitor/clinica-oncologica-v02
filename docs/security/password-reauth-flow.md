# Password Re-authentication Security Flow

## Overview

This document describes the security implementation for password change operations in the Hormonia oncology clinic system. The implementation follows defense-in-depth principles with multiple layers of validation.

## Security Architecture

### Multi-Layer Validation

1. **Client-Side Firebase Re-authentication** (Layer 1)
2. **Server-Side Firebase Auth API Validation** (Layer 2)
3. **Rate Limiting** (Layer 3)
4. **Session Invalidation** (Layer 4)

## Implementation Details

### 1. Client-Side Re-authentication (Frontend)

**Location**: `frontend-hormonia/src/hooks/usePasswordChange.ts`

```typescript
// Step 1: Re-authenticate with Firebase
const credential = EmailAuthProvider.credential(
  user.email,
  data.current_password
)
await reauthenticateWithCredential(user, credential)
```

**Purpose**:
- First line of defense
- Validates current password before API call
- Prevents unnecessary API requests
- Provides immediate user feedback

**Error Handling**:
- `auth/wrong-password`: "Senha atual incorreta"
- `auth/too-many-requests`: Rate limiting message
- `auth/network-request-failed`: Network error message

### 2. Server-Side Validation (Backend)

**Location**: `backend-hormonia/app/api/v1/auth.py`

```python
# Step 2: Validate via Firebase Auth REST API
verify_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
verify_response = requests.post(verify_url, json={
    "email": current_user.email,
    "password": password_data.current_password,
    "returnSecureToken": True
})
```

**Purpose**:
- Second line of defense (defense in depth)
- Protects against client-side tampering
- Server-side verification ensures authenticity
- Validates Firebase UID matches

**Validation Steps**:
1. Check HTTP status code (200 = valid)
2. Verify returned `localId` matches user's Firebase UID
3. Reject request if validation fails

### 3. Rate Limiting

**Implementation**: FastAPI rate limiter + Redis

```python
@limiter.limit("3/hour")  # 3 attempts per hour per IP
```

**Additional Check**:
```python
check_password_change_rate_limit(
    firebase_uid,
    max_attempts=3,
    window_seconds=3600
)
```

**Purpose**:
- Prevent brute force attacks
- Applied AFTER password validation (avoid rate limit bypass)
- Per-user and per-IP limits

### 4. Session Invalidation

**Location**: `backend-hormonia/app/api/v1/auth.py`

```python
# Invalidate all user sessions
firebase_cache.invalidate_all_user_sessions(firebase_uid)
```

**Purpose**:
- Force re-login with new password
- Prevent hijacked sessions from remaining active
- Security best practice after password change

## Request Flow Diagram

```
┌─────────────┐
│   User      │
│  Settings   │
└──────┬──────┘
       │ Enter current & new password
       ▼
┌─────────────────────────────────────┐
│  ReAuthenticationModal              │
│  (Client-Side Validation)           │
└──────┬──────────────────────────────┘
       │ Firebase reauthenticate()
       ▼
┌─────────────────────────────────────┐
│  usePasswordChange Hook             │
│  - Client-side Firebase validation  │
│  - Send to backend if valid         │
└──────┬──────────────────────────────┘
       │ POST /api/v1/auth/password
       ▼
┌─────────────────────────────────────┐
│  Backend Password Change Endpoint   │
│  1. Verify current password (API)   │
│  2. Check rate limit                │
│  3. Update password (Admin SDK)     │
│  4. Invalidate all sessions         │
└──────┬──────────────────────────────┘
       │ Success
       ▼
┌─────────────────────────────────────┐
│  Force Logout & Redirect to Login   │
└─────────────────────────────────────┘
```

## API Endpoints

### PUT /api/v1/auth/password

**Request**:
```json
{
  "current_password": "string (min 8 characters)",
  "new_password": "string (min 8 characters)"
}
```

**Response** (Success):
```json
{
  "success": true,
  "message": "Senha alterada com sucesso. Por favor, faça login novamente com sua nova senha."
}
```

**Response** (Error - Wrong Password):
```json
{
  "detail": "Senha atual incorreta. Por favor, verifique e tente novamente."
}
```

**Response** (Error - Rate Limit):
```json
{
  "detail": "Muitas tentativas de alteração de senha. Por favor, tente novamente mais tarde."
}
```

## Security Considerations

### Why Double Validation?

**Defense in Depth**: Even if client-side validation is bypassed (e.g., via modified JavaScript), server-side validation ensures security.

**Example Attack Scenario**:
1. Attacker modifies client code to skip re-authentication
2. Attacker sends direct API request with wrong current_password
3. Server-side validation catches this and rejects the request

### Why Validate Before Rate Limiting?

**Order of Operations**:
```python
# 1. Validate password FIRST
verify_current_password()

# 2. Check rate limit AFTER
check_rate_limit()
```

**Reason**: Prevents attackers from using rate limiting as an oracle to detect valid vs invalid passwords.

### Why Invalidate All Sessions?

**Scenario**:
1. User realizes their password was compromised
2. User changes password
3. Attacker's existing session should be invalidated immediately

**Implementation**: Forces re-login on all devices, ensuring only the legitimate user with the new password can access the account.

## Frontend Components

### ReAuthenticationModal

**Location**: `frontend-hormonia/src/components/auth/ReAuthenticationModal.tsx`

**Features**:
- Clean, accessible UI
- Loading states during validation
- Error message display
- Auto-clear on close
- Keyboard navigation support

**Props**:
```typescript
interface ReAuthenticationModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: (password: string) => Promise<void>
  title?: string
  description?: string
  error?: string | null
}
```

### usePasswordChange Hook

**Location**: `frontend-hormonia/src/hooks/usePasswordChange.ts`

**Features**:
- Firebase re-authentication
- Backend API integration
- Error state management
- Auto-logout after success

**Usage**:
```typescript
const { changePassword, isChangingPassword, error } = usePasswordChange()

await changePassword({
  current_password: "current",
  new_password: "new123",
})
```

## Testing

### E2E Tests

**Location**: `tests/e2e/password-reauth.spec.ts`

**Test Coverage**:
- ✅ Successful password change flow
- ✅ Wrong current password rejection
- ✅ Password confirmation mismatch
- ✅ Minimum password length validation
- ✅ All sessions invalidated after change
- ✅ Loading states during process
- ✅ Network error handling
- ✅ Rate limiting enforcement
- ✅ Form cleared after success
- ✅ Keyboard navigation
- ✅ ARIA labels for accessibility

### Unit Tests

**Location**: `tests/unit/ReAuthenticationModal.test.tsx`

**Test Coverage**:
- ✅ Component rendering
- ✅ Custom title/description
- ✅ Error message display
- ✅ Form submission
- ✅ Validation errors
- ✅ Loading states
- ✅ Form clearing on close
- ✅ Cancel button behavior
- ✅ Async callbacks
- ✅ Accessibility attributes
- ✅ Error handling

## Configuration

### Environment Variables

**Backend** (`.env`):
```bash
# Required for password validation
FIREBASE_WEB_API_KEY=your_firebase_web_api_key
FIREBASE_ADMIN_PROJECT_ID=your_project_id
FIREBASE_ADMIN_PRIVATE_KEY=your_private_key
FIREBASE_ADMIN_CLIENT_EMAIL=your_client_email

# Session management
FIREBASE_SESSION_TTL=86400  # 24 hours
```

**Frontend** (`.env`):
```bash
VITE_FIREBASE_API_KEY=your_firebase_web_api_key
VITE_API_BASE_URL=https://your-api-domain.com
```

## Monitoring & Logging

### Backend Logging

```python
# Success
logger.info(f"Current password validated successfully for user {user.id}")
logger.info(f"Password updated successfully for user {user.id}")
logger.info(f"Invalidated {n} sessions after password change")

# Failures
logger.warning(f"Current password validation failed for user {user.id}")
logger.error(f"Error validating current password: {error}")
```

### Metrics to Monitor

1. **Password change success rate**
2. **Failed validation attempts per user**
3. **Rate limit triggers per hour**
4. **Session invalidation count after password change**
5. **Average time for password change operation**

## Best Practices

### For Developers

1. **Never** skip current password validation
2. **Always** invalidate sessions after password change
3. **Always** rate limit password change endpoints
4. **Always** validate on both client and server
5. **Never** log passwords in any form
6. **Always** use HTTPS for password transmission

### For Security Auditors

1. Verify Firebase Auth integration is configured correctly
2. Check rate limiting is enforced
3. Confirm session invalidation works
4. Test with compromised client (modified JS)
5. Verify error messages don't leak information

## CSRF Protection

Password change endpoint is protected by CSRF token validation:

```python
# Applied via middleware
dependencies=[Depends(validate_csrf_token)]
```

**Implementation**: Double-submit cookie pattern with SameSite=Strict cookies.

## Compliance

This implementation satisfies:
- **OWASP A07:2021** - Identification and Authentication Failures
- **PCI DSS 8.2.3** - Password verification before change
- **NIST 800-63B** - Authentication and lifecycle management
- **LGPD** - Data protection requirements for healthcare

## Future Enhancements

1. **Multi-Factor Authentication (2FA)** before password change
2. **Password strength meter** in UI
3. **Breach database check** (Have I Been Pwned API)
4. **Email notification** on password change
5. **Audit trail** for all password changes
6. **Suspicious activity detection** (location/device change)

## Support

For security concerns or questions, contact:
- Security Team: security@hormonia.com
- Documentation: https://docs.hormonia.com/security/password-management
