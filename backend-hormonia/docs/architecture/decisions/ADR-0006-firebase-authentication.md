# ADR-0006: Firebase Admin SDK for Authentication

## Status

Accepted

Date: 2024-01-20

## Context

The Clínica Hormonia system requires secure authentication for:
- **Admin users**: System administrators with full access
- **Physicians**: Medical staff accessing patient data
- **Patients**: Limited access to their own quiz responses
- **Multi-factor authentication**: Enhanced security for sensitive medical data
- **Session management**: Token-based authentication for API access
- **Social login**: Google/email authentication options
- **HIPAA compliance**: Audit trails and secure credential storage

Requirements:
- Industry-standard authentication (OAuth 2.0, JWT)
- Multi-factor authentication (MFA) support
- Social provider integration (Google)
- Token refresh mechanism
- Role-based access control (RBAC)
- Audit logging of authentication events
- Secure password storage

## Decision

We will use **Firebase Admin SDK** for backend authentication and authorization, with Firebase Authentication for client-side auth flows.

Key features:
1. **JWT verification**: Validate Firebase ID tokens on backend
2. **Custom claims**: Store user roles (admin, physician, patient) in tokens
3. **Token refresh**: Automatic token refresh with refresh tokens
4. **MFA support**: Built-in 2FA with SMS/TOTP
5. **Social providers**: Google, email/password authentication
6. **User management**: Admin SDK for user CRUD operations
7. **Audit logs**: Firebase Auth logs all authentication events

## Consequences

### Positive Consequences

- **Security**: Industry-standard JWT authentication
- **Scalability**: Firebase handles auth infrastructure
- **MFA built-in**: 2FA support without custom implementation
- **Social login**: Google authentication out of the box
- **Token management**: Automatic refresh token handling
- **Audit trail**: Firebase logs all auth events
- **Developer productivity**: Less auth code to maintain
- **Free tier**: Generous free tier for MVP
- **Custom claims**: Store roles directly in JWT tokens

### Negative Consequences

- **Vendor lock-in**: Tied to Google Cloud Platform
- **Cost at scale**: Pricing increases with user count
- **Limited customization**: Must work within Firebase constraints
- **Cold start**: Initial token verification can be slow
- **Offline limitations**: Requires internet for auth
- **Migration complexity**: Hard to migrate away from Firebase

### Risks

- **Service outage**: Firebase downtime affects authentication
- **Price changes**: Google could change pricing model
- **Feature deprecation**: Firebase features could be deprecated
- **Compliance changes**: Firebase compliance certifications could change
- **Data residency**: User data stored in Google's infrastructure

## Alternatives Considered

### Alternative 1: Custom JWT with bcrypt

**Description**: Build custom authentication system with JWT and bcrypt

**Pros**:
- Full control over implementation
- No vendor lock-in
- No external costs
- Custom features possible

**Cons**:
- More code to maintain
- Need to implement MFA
- Manual token refresh logic
- No social login out of the box
- Security vulnerabilities to handle
- Audit logging needs custom implementation

**Why rejected**: Building secure auth is complex and risky for medical data

### Alternative 2: Auth0

**Description**: Third-party authentication as a service

**Pros**:
- Enterprise features
- Extensive social providers
- Good documentation
- Battle-tested security

**Cons**:
- Expensive ($240-840/month for our scale)
- Another vendor dependency
- More complex than Firebase
- Higher learning curve

**Why rejected**: Cost prohibitive for startup, Firebase meets requirements

### Alternative 3: AWS Cognito

**Description**: Amazon's authentication service

**Pros**:
- AWS ecosystem integration
- Competitive pricing
- Custom UI flexibility
- Good documentation

**Cons**:
- More complex setup than Firebase
- Steeper learning curve
- UI less polished
- Team unfamiliar with AWS
- Custom claims more complex

**Why rejected**: Firebase simpler and team has Google Cloud experience

### Alternative 4: Keycloak

**Description**: Open-source identity and access management

**Pros**:
- Free and open source
- Self-hosted option
- Full control
- SAML/OIDC support

**Cons**:
- Complex to set up and maintain
- Need to host infrastructure
- Smaller community than Firebase
- More operational overhead
- No social login out of the box

**Why rejected**: Too much operational overhead for startup

## Implementation Notes

### Firebase Initialization

```python
import firebase_admin
from firebase_admin import credentials, auth

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

class FirebaseAuthService:
    @staticmethod
    async def verify_token(id_token: str) -> dict:
        """Verify Firebase ID token and return user claims"""
        try:
            decoded_token = auth.verify_id_token(id_token)
            return {
                "uid": decoded_token["uid"],
                "email": decoded_token.get("email"),
                "role": decoded_token.get("role"),  # Custom claim
                "physician_id": decoded_token.get("physician_id"),
            }
        except auth.InvalidIdTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except auth.ExpiredIdTokenError:
            raise HTTPException(status_code=401, detail="Token expired")
```

### Custom Claims for RBAC

```python
async def set_user_role(uid: str, role: str, physician_id: str = None):
    """Set custom claims for user role"""
    custom_claims = {
        "role": role,  # "admin", "physician", "patient"
    }

    if role == "physician" and physician_id:
        custom_claims["physician_id"] = physician_id

    auth.set_custom_user_claims(uid, custom_claims)

    # Force token refresh on client
    return {"message": "Role updated, client must refresh token"}
```

### Role Resolution and Defaults

Role resolution follows a strict priority order:
1. **Firebase custom claims** (`role` or `roles`)
2. **Database role** (stored on the User model)
3. **Default role** (`doctor`)

When issuing tokens, set custom claims securely from the backend only:

```python
from firebase_admin import auth

auth.set_custom_user_claims(uid, {"role": "admin"})
```

Security considerations:
- Role values are validated against the `UserRole` enum (admin/doctor).
- Invalid or missing roles fall back to the database role or default doctor role.
- Role resolution decisions are logged for audit visibility.
- On role changes, invalidate Redis user cache to prevent stale permissions.

### Authentication Middleware

```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Extract and verify Firebase token from Authorization header"""
    token = credentials.credentials

    try:
        user_data = await FirebaseAuthService.verify_token(token)
        return user_data
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )

async def require_role(required_role: str):
    """Dependency to require specific role"""
    async def role_checker(user: dict = Depends(get_current_user)):
        if user.get("role") != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {required_role} role"
            )
        return user
    return role_checker

# Usage in endpoints
@router.get("/admin/users")
async def list_users(user: dict = Depends(require_role("admin"))):
    """Admin-only endpoint"""
    return {"users": []}
```

### User Management

```python
class UserManagementService:
    @staticmethod
    async def create_physician(email: str, password: str, full_name: str):
        """Create physician user with custom claims"""
        # Create Firebase user
        user = auth.create_user(
            email=email,
            password=password,
            display_name=full_name,
            email_verified=False
        )

        # Set physician role
        auth.set_custom_user_claims(user.uid, {
            "role": "physician",
            "physician_id": str(uuid.uuid4())
        })

        # Send email verification
        link = auth.generate_email_verification_link(email)
        await send_verification_email(email, link)

        return {"uid": user.uid, "email": email}

    @staticmethod
    async def delete_user(uid: str):
        """Delete user from Firebase"""
        auth.delete_user(uid)
        return {"message": "User deleted"}

    @staticmethod
    async def list_users(limit: int = 100):
        """List all users"""
        users = auth.list_users(max_results=limit)
        return [
            {
                "uid": user.uid,
                "email": user.email,
                "disabled": user.disabled,
                "custom_claims": user.custom_claims
            }
            for user in users.iterate_all()
        ]
```

### Token Refresh Flow

```python
# Frontend refreshes token before expiry
async def refresh_firebase_token(refresh_token: str) -> str:
    """
    Client-side: Use Firebase SDK to refresh token
    Backend: Verify refreshed ID token
    """
    # Firebase SDK handles refresh automatically
    # Backend just verifies the new ID token
    pass
```

### Multi-Factor Authentication

```python
# Enable MFA for user (client-side with Firebase SDK)
# Backend just verifies that MFA is enabled
async def check_mfa_enabled(uid: str) -> bool:
    """Check if user has MFA enabled"""
    user = auth.get_user(uid)
    return len(user.multi_factor.enrolled_factors) > 0
```

### Audit Logging

```python
async def log_authentication_event(
    event_type: str,
    user_id: str,
    ip_address: str,
    success: bool
):
    """Log authentication events for audit"""
    await db.execute(
        """
        INSERT INTO auth_audit_log (event_type, user_id, ip_address, success, timestamp)
        VALUES (:event_type, :user_id, :ip_address, :success, NOW())
        """,
        {
            "event_type": event_type,
            "user_id": user_id,
            "ip_address": ip_address,
            "success": success
        }
    )
```

### Migration Path

1. ✅ Firebase project created and configured
2. ✅ Admin SDK initialized in backend
3. ✅ Custom claims for RBAC implemented
4. ✅ Authentication middleware created
5. ✅ User management endpoints
6. ✅ Frontend Firebase SDK integration
7. 🔄 MFA enrollment UI
8. 🔄 Email verification flow
9. 🔄 Password reset functionality

### Security Best Practices

1. **Token verification**: Always verify tokens server-side
2. **HTTPS only**: Never send tokens over HTTP
3. **Token storage**: Use httpOnly cookies or secure storage
4. **Refresh tokens**: Rotate refresh tokens regularly
5. **Custom claims**: Limit size (<1000 bytes)
6. **Rate limiting**: Prevent brute force attacks
7. **Service account**: Secure Firebase service account key

## References

- [Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)
- [Firebase Authentication](https://firebase.google.com/docs/auth)
- [Custom Claims](https://firebase.google.com/docs/auth/admin/custom-claims)
- [Firebase Security Rules](https://firebase.google.com/docs/rules)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

## Metadata

- **Author**: Security Team
- **Reviewers**: Backend Team, Compliance Officer
- **Last Updated**: 2024-01-20
- **Related ADRs**: ADR-0001 (FastAPI), ADR-0010 (Security)
- **Tags**: security, authentication, firebase, identity
