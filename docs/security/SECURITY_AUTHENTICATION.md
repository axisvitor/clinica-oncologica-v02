# Security and Authentication Guide

**Project**: Clínica Oncológica - Sistema Hormonia
**Last Updated**: 2025-11-12
**Security Level**: HIPAA-Compliant

## Overview

This document outlines the comprehensive security architecture, authentication mechanisms, and best practices for Sistema Hormonia. Given the sensitive nature of healthcare data, security is paramount.

## Table of Contents

1. [Authentication Architecture](#authentication-architecture)
2. [Authorization & Access Control](#authorization--access-control)
3. [Data Security](#data-security)
4. [API Security](#api-security)
5. [Infrastructure Security](#infrastructure-security)
6. [Security Best Practices](#security-best-practices)
7. [Compliance](#compliance)

## Authentication Architecture

### Overview

Sistema Hormonia uses a multi-layered authentication approach combining JWT tokens with Firebase Authentication.

```
User Login Request
     ↓
Firebase Authentication
     ↓
Generate JWT Tokens
 ├── Access Token (30 min)
 └── Refresh Token (7 days)
     ↓
Store in Redis Whitelist
     ↓
Return to Client
```

### JWT Token Structure

**Access Token**:
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "doctor",
  "permissions": ["read:patients", "write:messages"],
  "exp": 1699999999,
  "iat": 1699996399,
  "jti": "unique-token-id"
}
```

**Refresh Token**:
```json
{
  "sub": "user_id",
  "type": "refresh",
  "exp": 1700599999,
  "iat": 1699996399,
  "jti": "unique-refresh-id"
}
```

### Token Lifecycle

```python
# Token generation
from app.core.auth import create_tokens

access_token, refresh_token = create_tokens(
    user_id=user.id,
    role=user.role,
    permissions=user.permissions
)

# Token validation
from app.core.auth import verify_token

payload = verify_token(access_token)
user_id = payload["sub"]
role = payload["role"]

# Token refresh
from app.core.auth import refresh_access_token

new_access_token = refresh_access_token(refresh_token)

# Token revocation
from app.core.auth import revoke_tokens

revoke_tokens(user_id)  # Blacklist all user tokens
```

### Token Storage

**Backend** (Redis):
```python
# Whitelist active tokens
redis.setex(
    f"token:{token_jti}",
    token_expiry,
    user_id
)

# Blacklist revoked tokens
redis.setex(
    f"blacklist:{token_jti}",
    token_expiry,
    "revoked"
)
```

**Frontend** (Secure HTTP-only Cookies):
```typescript
// Access token in memory
const authContext = {
  accessToken: string;  // In memory only
  refreshToken: string; // HTTP-only cookie
};

// Auto-refresh 5 minutes before expiry
useEffect(() => {
  const refreshInterval = setInterval(() => {
    if (shouldRefreshToken(accessToken)) {
      refreshAccessToken();
    }
  }, 60000); // Check every minute

  return () => clearInterval(refreshInterval);
}, [accessToken]);
```

## Authorization & Access Control

### Role-Based Access Control (RBAC)

#### Role Hierarchy

```
admin
  ├── All permissions
  └── User management

doctor
  ├── Patient management
  ├── Quiz management
  ├── Message sending
  └── Reports viewing

patient
  ├── Own data viewing
  ├── Quiz completion
  └── Message viewing

service_provider
  ├── System integration
  └── API access

system
  ├── Automated tasks
  └── Internal operations

viewer
  ├── Read-only access
  └── Analytics viewing

external_integration
  ├── Limited API access
  └── Webhook endpoints
```

#### Permission System

```python
# Permission definition
from enum import Enum

class Permission(str, Enum):
    # Patient permissions
    READ_PATIENTS = "read:patients"
    WRITE_PATIENTS = "write:patients"
    DELETE_PATIENTS = "delete:patients"

    # Message permissions
    READ_MESSAGES = "read:messages"
    SEND_MESSAGES = "send:messages"

    # Quiz permissions
    READ_QUIZ = "read:quiz"
    CREATE_QUIZ = "create:quiz"
    GRADE_QUIZ = "grade:quiz"

    # Admin permissions
    MANAGE_USERS = "manage:users"
    MANAGE_ROLES = "manage:roles"
    VIEW_AUDIT = "view:audit"
```

#### Permission Checks

```python
# Decorator for permission checks
from app.core.auth import require_permission

@router.get("/patients")
@require_permission(Permission.READ_PATIENTS)
async def list_patients(
    current_user: User = Depends(get_current_user)
):
    # Only users with READ_PATIENTS permission can access
    return patients

# Manual permission check
from app.core.auth import has_permission

if not has_permission(current_user, Permission.WRITE_PATIENTS):
    raise PermissionDeniedError("Cannot modify patients")
```

### Row-Level Security (RLS)

#### PostgreSQL RLS Policies

```sql
-- Enable RLS on patients table
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Doctors can only see their own patients
CREATE POLICY doctor_patients ON patients
    FOR ALL
    TO doctor
    USING (doctor_id = current_setting('app.current_user_id')::int);

-- Patients can only see their own data
CREATE POLICY patient_own_data ON patients
    FOR SELECT
    TO patient
    USING (id = current_setting('app.current_user_id')::int);

-- Admins can see all
CREATE POLICY admin_all_patients ON patients
    FOR ALL
    TO admin
    USING (true);
```

#### RLS in Application

```python
# Set current user for RLS
from app.core.database import set_current_user_context

with set_current_user_context(user_id, role):
    # All queries respect RLS policies
    patients = db.query(Patient).all()
    # Returns only authorized patients
```

## Data Security

### Data Classification

| Level | Description | Examples | Encryption |
|-------|-------------|----------|------------|
| **Critical** | PII, PHI | Patient names, medical data | At rest + transit |
| **Sensitive** | Authentication | Passwords, tokens | At rest + transit |
| **Confidential** | Business | Analytics, reports | In transit |
| **Public** | General | Public content | Optional |

### Encryption

#### In Transit (TLS 1.3)

```nginx
# Nginx TLS configuration
server {
    listen 443 ssl http2;
    ssl_protocols TLSv1.3;
    ssl_ciphers 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384';
    ssl_prefer_server_ciphers on;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
}
```

#### At Rest (Database)

```python
# Field-level encryption for sensitive data
from cryptography.fernet import Fernet
from app.core.encryption import encrypt_field, decrypt_field

# Encrypt before storing
encrypted_ssn = encrypt_field(patient.ssn)
patient.encrypted_ssn = encrypted_ssn
db.add(patient)

# Decrypt when retrieving
decrypted_ssn = decrypt_field(patient.encrypted_ssn)
```

### Password Security

```python
# Password hashing with bcrypt
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # High cost factor
)

# Hash password
hashed = pwd_context.hash(plain_password)

# Verify password
is_valid = pwd_context.verify(plain_password, hashed)

# Password requirements
MIN_LENGTH = 12
REQUIRE_UPPERCASE = True
REQUIRE_LOWERCASE = True
REQUIRE_DIGITS = True
REQUIRE_SPECIAL = True
```

## API Security

### Request Validation

```python
# Input validation with Pydantic
from pydantic import BaseModel, validator, EmailStr

class PatientCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str

    @validator('name')
    def validate_name(cls, v):
        if len(v) < 3 or len(v) > 100:
            raise ValueError('Name must be 3-100 characters')
        if not v.replace(' ', '').isalpha():
            raise ValueError('Name must contain only letters')
        return v.strip()

    @validator('phone')
    def validate_phone(cls, v):
        # Brazilian phone format
        if not re.match(r'^\+55\d{10,11}$', v):
            raise ValueError('Invalid phone format')
        return v
```

### Rate Limiting

```python
# FastAPI rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(request: Request):
    # Login logic
    pass

# Custom rate limiting with Redis
from app.core.rate_limit import check_rate_limit

@router.get("/api/patients")
async def list_patients(request: Request):
    if not check_rate_limit(request.client.host, limit=100, period=60):
        raise HTTPException(429, "Too many requests")
    # Return patients
```

### CORS Configuration

```python
# Strict CORS settings
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.hormonia.com",
        "https://quiz.hormonia.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)
```

### Security Headers

```python
# Security headers middleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = \
            "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = \
            "default-src 'self'; script-src 'self' 'unsafe-inline'"

        return response

app.add_middleware(SecurityHeadersMiddleware)
```

### SQL Injection Prevention

```python
# ✅ SAFE: Using ORM
patients = db.query(Patient).filter(
    Patient.name.ilike(f"%{search_term}%")
).all()

# ✅ SAFE: Parameterized raw SQL
patients = db.execute(
    text("SELECT * FROM patients WHERE name ILIKE :search"),
    {"search": f"%{search_term}%"}
).fetchall()

# ❌ UNSAFE: String concatenation
# NEVER DO THIS
patients = db.execute(
    f"SELECT * FROM patients WHERE name ILIKE '%{search_term}%'"
).fetchall()
```

### XSS Prevention

```python
# Backend: Sanitize HTML input
from bleach import clean

def sanitize_html(html: str) -> str:
    allowed_tags = ['p', 'br', 'strong', 'em', 'u']
    return clean(html, tags=allowed_tags, strip=True)

# Frontend: Use DOMPurify
import DOMPurify from 'dompurify';

const sanitized = DOMPurify.sanitize(userInput);
```

## Infrastructure Security

### Environment Variables

```bash
# ✅ GOOD: Use environment variables
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=your-secret-key-min-32-chars

# ✅ GOOD: Use secrets management
# AWS Secrets Manager, Azure Key Vault, etc.

# ❌ BAD: Hardcoded secrets
# NEVER commit secrets to Git
```

### Database Security

```python
# Connection with SSL
DATABASE_URL = "postgresql://user:pass@host:5432/db?sslmode=require"

# Connection pooling limits
SQLALCHEMY_POOL_SIZE = 5
SQLALCHEMY_MAX_OVERFLOW = 10
SQLALCHEMY_POOL_TIMEOUT = 30

# Prepared statements (automatic with SQLAlchemy)
# Prevents SQL injection
```

### Redis Security

```python
# Redis with password
REDIS_URL = "redis://:password@host:6379/0"

# Redis SSL
REDIS_URL = "rediss://host:6380/0"
redis_client = Redis.from_url(
    REDIS_URL,
    ssl_cert_reqs="required",
    ssl_ca_certs="/path/to/ca.pem"
)
```

## Security Best Practices

### Development

1. **Never commit secrets**
   - Use `.env` files (in `.gitignore`)
   - Use secrets management services
   - Rotate keys regularly

2. **Keep dependencies updated**
   ```bash
   # Check for vulnerabilities
   pip-audit
   npm audit
   ```

3. **Use security linters**
   ```bash
   # Python
   bandit -r app/

   # TypeScript
   npm run lint:security
   ```

4. **Regular security testing**
   - Automated security scans
   - Penetration testing
   - Code reviews

### Production

1. **Principle of Least Privilege**
   - Minimal permissions for services
   - Separate production/development access
   - Regular access audits

2. **Monitoring & Alerts**
   - Failed login attempts
   - Unusual API activity
   - Data access patterns
   - System vulnerabilities

3. **Backup & Recovery**
   - Automated daily backups
   - Encrypted backup storage
   - Regular restore testing
   - Disaster recovery plan

4. **Incident Response**
   - Security incident playbook
   - Defined escalation path
   - Post-incident reviews

## Compliance

### HIPAA Compliance

Sistema Hormonia follows HIPAA requirements for protected health information (PHI):

1. **Administrative Safeguards**
   - Security management process
   - Workforce training
   - Access authorization

2. **Physical Safeguards**
   - Facility access controls
   - Workstation security
   - Device encryption

3. **Technical Safeguards**
   - Access controls
   - Audit controls
   - Integrity controls
   - Transmission security

### LGPD Compliance (Brazilian GDPR)

1. **Data Subject Rights**
   - Right to access
   - Right to correction
   - Right to deletion
   - Right to portability

2. **Implementation**
   ```python
   # Data export
   @router.get("/me/export")
   async def export_my_data(user: User = Depends(get_current_user)):
       return generate_data_export(user.id)

   # Data deletion
   @router.delete("/me")
   async def delete_my_account(user: User = Depends(get_current_user)):
       anonymize_user_data(user.id)
       return {"message": "Account deleted"}
   ```

### Audit Logging

```python
# Audit log model
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    action = Column(String)
    resource = Column(String)
    resource_id = Column(Integer)
    changes = Column(JSON)
    ip_address = Column(String)
    user_agent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Log security events
def log_security_event(
    user_id: int,
    action: str,
    resource: str,
    ip_address: str
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
```

## Security Incident Response

### Incident Classification

- **P1 (Critical)**: Data breach, system compromise
- **P2 (High)**: Unauthorized access attempt
- **P3 (Medium)**: Policy violation
- **P4 (Low)**: Suspicious activity

### Response Steps

1. **Identify**: Detect and confirm incident
2. **Contain**: Limit damage and prevent spread
3. **Eradicate**: Remove threat from system
4. **Recover**: Restore normal operations
5. **Review**: Post-incident analysis

## Resources

- **OWASP Top 10**: https://owasp.org/Top10/
- **HIPAA Security Rule**: https://www.hhs.gov/hipaa/for-professionals/security/
- **LGPD Guide**: https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd

---

**Last Updated**: 2025-11-12
**Security Contact**: security@hormonia.com
**Next Review**: 2025-12-12
