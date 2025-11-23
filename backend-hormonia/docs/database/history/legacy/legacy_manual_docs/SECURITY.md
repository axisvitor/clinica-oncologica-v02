# Database Security

Security architecture, RBAC implementation, and compliance features for the Hormonia Backend database.

## Table of Contents

- [Security Overview](#security-overview)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Authentication & Sessions](#authentication--sessions)
- [Data Encryption](#data-encryption)
- [Audit Trail](#audit-trail)
- [Access Control](#access-control)
- [Security Best Practices](#security-best-practices)
- [Compliance](#compliance)

---

## Security Overview

### Security Layers

1. **Authentication** - Firebase Authentication + local credentials
2. **Authorization** - Role-based access control (RBAC)
3. **Session Management** - Secure session tracking with device fingerprinting
4. **Audit Logging** - Comprehensive security event tracking
5. **Data Protection** - Encryption support and data isolation
6. **Network Security** - IP tracking and rate limiting

### Security-Related Tables

| Table | Purpose | Features |
|-------|---------|----------|
| `users` | User accounts | Password hashing, account lockout, Firebase sync |
| `sessions` | Active sessions | Device tracking, risk scoring, revocation |
| `audit_logs` | Security events | Authentication, authorization, suspicious activity |
| `patient_onboarding_saga` | Transaction audit | Distributed transaction tracking |
| `webhook_idempotency` | Replay protection | Idempotency keys, TTL expiration |

---

## Role-Based Access Control (RBAC)

### User Roles

```python
class UserRole(enum.Enum):
    ADMIN = "admin"    # Full system access
    DOCTOR = "doctor"  # Patient management access
```

### Role Permissions

**ADMIN:**
- User management (create, update, delete users)
- System configuration
- View all patients across all doctors
- Access audit logs
- Generate system reports

**DOCTOR:**
- Manage own patients only
- Create/update/delete own patient records
- View own patient data
- Schedule appointments for own patients
- Prescribe medications for own patients
- Generate reports for own patients

### Data Isolation

**Doctor-Scoped Data:**
- Patients are scoped to `doctor_id`
- Composite unique constraints prevent cross-doctor duplicates:
  ```sql
  UNIQUE (email, doctor_id)
  UNIQUE (cpf, doctor_id)
  UNIQUE (phone, doctor_id)
  ```

**Row-Level Security (Future):**
```sql
-- Enable RLS on patients table
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Policy: Doctors can only see their own patients
CREATE POLICY doctor_patients_policy ON patients
FOR ALL
TO app_user
USING (doctor_id = current_setting('app.current_user_id')::uuid);

-- Policy: Admins can see all patients
CREATE POLICY admin_patients_policy ON patients
FOR ALL
TO app_admin
USING (true);
```

---

## Authentication & Sessions

### Authentication Methods

**Local Authentication:**
- Email + password
- Bcrypt hashed passwords (cost factor 12)
- Stored in `users.hashed_password`

**Firebase Authentication:**
- Google, Email/Password, Phone
- Firebase UID stored in `users.firebase_uid`
- Custom claims in `users.firebase_custom_claims` (JSONB)
- Last sync tracked in `users.last_firebase_sync`

### Account Security

**Password Requirements:**
- Minimum 8 characters
- Complexity enforced by application
- Password change tracking in `users.last_password_change`
- Force password change via `users.force_change_password`

**Account Lockout:**
```sql
-- Track failed login attempts
users.failed_login_attempts (INTEGER)
users.is_locked (BOOLEAN)
users.locked_until (TIMESTAMPTZ)
```

**Lockout Logic:**
- 5 failed attempts → account locked
- Lockout duration: 30 minutes (configurable)
- Auto-unlock after `locked_until` expires
- Audit log entry for each failed attempt

### Session Management

**Session Table Fields:**
```sql
sessions {
  session_token    VARCHAR(500) UNIQUE  -- JWT or session ID
  refresh_token    VARCHAR(500) UNIQUE  -- Refresh token
  device_id        VARCHAR(200)         -- Device fingerprint
  device_name      VARCHAR(200)         -- User agent
  device_type      VARCHAR(50)          -- mobile, desktop, tablet
  ip_address       VARCHAR(45)          -- IPv6 compatible
  user_agent       TEXT                 -- Full user agent string
  location         JSONB                -- Geolocation data
  last_activity    TIMESTAMPTZ          -- Activity tracking
  expires_at       TIMESTAMPTZ          -- Session expiration
  is_active        BOOLEAN              -- Active status
  is_suspicious    BOOLEAN              -- Security flag
  risk_score       VARCHAR(50)          -- low, medium, high
}
```

**Session Security Features:**
1. **Device Fingerprinting** - Track device_id, user_agent, IP
2. **Geolocation** - Store location data in JSONB
3. **Risk Scoring** - Flag suspicious sessions
4. **Activity Tracking** - Update `last_activity` on each request
5. **Expiration** - Automatic session expiry
6. **Revocation** - Manual session termination

**Security Checks:**
```python
# Detect session hijacking
if session.ip_address != request.ip:
    mark_suspicious(session)

# Detect unusual location
if session.location != request.location:
    verify_mfa()

# Enforce session timeout
if session.last_activity < now() - timedelta(hours=24):
    invalidate_session(session)
```

---

## Data Encryption

### Encryption Support (Future Implementation)

**Field-Level Encryption:**
```sql
-- Encrypted patient email (Phase 3)
CREATE TABLE patients (
  email_encrypted BYTEA,  -- AES-256-GCM encrypted
  email_hash      VARCHAR(64),  -- SHA-256 hash for searching
  ...
);

-- Searchable encryption
CREATE INDEX idx_patients_email_hash ON patients(email_hash);
```

**Encryption Functions:**
```sql
-- Encrypt field
SELECT pgp_sym_encrypt('sensitive_data', 'encryption_key') AS encrypted;

-- Decrypt field
SELECT pgp_sym_decrypt(encrypted_column, 'encryption_key') AS decrypted;

-- Hash for searching
SELECT encode(sha256('search_term'::bytea), 'hex') AS search_hash;
```

**Encryption Key Management:**
- Application-level encryption keys
- Key rotation support
- Separate keys per tenant (doctor)
- Hardware Security Module (HSM) integration ready

### Sensitive Data Fields

**Currently Stored in Plain Text (Future Encryption Candidates):**
- `patients.email`
- `patients.cpf`
- `patients.phone`
- `patients.birth_date`
- `users.email`
- `sessions.ip_address`

**Already Protected:**
- `users.hashed_password` (Bcrypt hashed)
- Session tokens (JWT signed)

---

## Audit Trail

See [AUDIT_TRAIL.md](./AUDIT_TRAIL.md) for comprehensive audit logging documentation.

**Security-Related Audit Events:**
```python
# Authentication Events
LOGIN_SUCCESS
LOGIN_FAILURE
LOGOUT
TOKEN_REFRESH
SESSION_CREATED
SESSION_EXPIRED
SESSION_INVALIDATED

# Authorization Events
ACCESS_DENIED
PERMISSION_CHANGED
ROLE_CHANGED

# Account Security Events
PASSWORD_CHANGED
PASSWORD_RESET_REQUESTED
ACCOUNT_LOCKED
ACCOUNT_UNLOCKED
SUSPICIOUS_ACTIVITY
RATE_LIMIT_EXCEEDED

# Security Violations
INVALID_TOKEN
CSRF_VIOLATION
```

---

## Access Control

### API-Level Authorization

**Endpoint Protection:**
```python
@require_auth
@require_role(UserRole.DOCTOR)
def get_patient(patient_id: UUID):
    # Verify patient belongs to current doctor
    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.doctor_id == current_user.id
    ).first()

    if not patient:
        raise HTTPException(403, "Access denied")

    return patient
```

**RBAC Decorator:**
```python
def require_role(*roles: UserRole):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                audit_log(ACCESS_DENIED, ...)
                raise HTTPException(403, "Insufficient permissions")
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### Database-Level Access Control

**PostgreSQL Roles:**
```sql
-- Application user (read/write)
CREATE ROLE app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;

-- Read-only user (reports)
CREATE ROLE app_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

-- Admin user (full access)
CREATE ROLE app_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_admin;
```

**Connection Credentials:**
- Separate database users per environment
- Least privilege principle
- No superuser access for application

---

## Security Best Practices

### Password Security

**Hashing:**
```python
import bcrypt

# Hash password
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))

# Verify password
if bcrypt.checkpw(password.encode('utf-8'), hashed):
    # Password correct
```

**Requirements:**
- Bcrypt cost factor: 12 (adjustable)
- Salt automatically generated
- Password history tracking (prevent reuse)

### Session Security

**Best Practices:**
1. **Rotate session tokens** after authentication
2. **Bind sessions to IP and device** (detect hijacking)
3. **Implement session timeout** (idle + absolute)
4. **Revoke on logout** (server-side invalidation)
5. **Monitor for suspicious activity** (unusual IP, location)

### SQL Injection Prevention

**SQLAlchemy ORM:**
```python
# ✅ Safe (parameterized query)
patients = db.query(Patient).filter(Patient.email == user_input).all()

# ❌ Unsafe (string concatenation)
db.execute(f"SELECT * FROM patients WHERE email = '{user_input}'")
```

**Prepared Statements:**
```python
# ✅ Safe
stmt = select(Patient).where(Patient.email == user_input)
result = db.execute(stmt).all()
```

### CSRF Protection

**Implementation:**
- CSRF tokens for state-changing requests
- SameSite cookie attribute
- Origin header validation
- Audit CSRF violations

### Rate Limiting

**Application-Level:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/v2/auth/login")
@limiter.limit("5/minute")
def login():
    # Rate limited to 5 attempts per minute
    ...
```

**Database Tracking:**
```sql
-- Track in audit_logs
event_type = 'rate_limit_exceeded'
event_metadata = {
  "endpoint": "/api/v2/auth/login",
  "rate_limit": "5/minute",
  "attempts": 6
}
```

---

## Compliance

### HIPAA Compliance

**Required Features:**
- ✅ Audit trail for all PHI access
- ✅ User authentication and authorization
- ✅ Session management and timeout
- ✅ Access control (RBAC)
- 🔜 Data encryption (at rest and in transit)
- ✅ Automatic session expiration
- ✅ Account lockout after failed attempts
- ✅ Audit log retention

**PHI (Protected Health Information):**
- Patient name, email, phone, CPF, birth_date
- Medical diagnosis, treatment data
- Quiz responses, medical reports
- All stored in `patients` table and related tables

**Audit Requirements:**
- Log all PHI access (SELECT queries)
- Track PHI modifications (INSERT, UPDATE, DELETE)
- Immutable audit logs
- Minimum 6-year retention

### LGPD/GDPR Compliance

**Data Subject Rights:**
- ✅ Right to access (export patient data)
- ✅ Right to rectification (update patient data)
- ✅ Right to erasure (soft delete via `deleted_at`)
- ✅ Right to data portability (JSON export)
- ✅ Consent management (`consents` table)

**Soft Delete Implementation:**
```sql
-- Soft delete patient
UPDATE patients SET deleted_at = NOW() WHERE id = '...';

-- Exclude deleted patients from queries
SELECT * FROM patients WHERE deleted_at IS NULL;

-- Permanent deletion (after retention period)
DELETE FROM patients WHERE deleted_at < NOW() - INTERVAL '7 years';
```

**Consent Tracking:**
- Granular consent types (treatment, data sharing, research)
- Consent versioning
- Digital signature support
- Revocation tracking

### SOC 2 Compliance

**Security Controls:**
- ✅ User access management (RBAC)
- ✅ Audit logging
- ✅ Session management
- ✅ Password complexity enforcement
- ✅ Account lockout
- 🔜 Data encryption
- ✅ Security event monitoring

---

## Security Monitoring

### Real-Time Alerts

**Security Events to Monitor:**
```python
# Brute force attack detection
SELECT user_email, COUNT(*) as attempts
FROM audit_logs
WHERE event_type = 'login_failure'
AND created_at > NOW() - INTERVAL '5 minutes'
GROUP BY user_email
HAVING COUNT(*) >= 5;

# Suspicious IP detection
SELECT ip_address, COUNT(DISTINCT user_id) as unique_users
FROM audit_logs
WHERE event_type = 'login_success'
AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY ip_address
HAVING COUNT(DISTINCT user_id) > 5;

# Session hijacking detection
SELECT s.id, s.user_id, s.ip_address, a.ip_address as audit_ip
FROM sessions s
JOIN audit_logs a ON a.user_id = s.user_id
WHERE s.is_active = true
AND s.ip_address != a.ip_address
AND a.created_at > s.created_at;
```

### Security Dashboards

**Metrics to Track:**
- Failed login attempts (by user, IP)
- Active sessions (by user, device, IP)
- Suspicious activities
- Access denied events
- Account lockouts
- CSRF violations
- Rate limit exceeded

---

## Security Recommendations

### Immediate Actions

1. ✅ **Enable HTTPS** - Force TLS 1.2+ for all connections
2. ✅ **Implement rate limiting** - Prevent brute force attacks
3. ✅ **Enable audit logging** - Track all security events
4. ✅ **Configure session timeout** - 24-hour idle timeout
5. ✅ **Enforce password complexity** - Minimum 8 characters

### Short-Term (1-3 months)

1. 🔜 **Implement field-level encryption** - Encrypt sensitive PHI
2. 🔜 **Enable Row-Level Security** - PostgreSQL RLS policies
3. 🔜 **Add MFA support** - Two-factor authentication
4. 🔜 **Implement IP allowlisting** - Restrict admin access by IP
5. 🔜 **Add security headers** - HSTS, CSP, X-Frame-Options

### Long-Term (3-6 months)

1. 🔜 **Implement HSM** - Hardware security module for key management
2. 🔜 **Add penetration testing** - Regular security audits
3. 🔜 **Implement SIEM** - Security information and event management
4. 🔜 **Add intrusion detection** - Network and host-based IDS
5. 🔜 **Implement backup encryption** - Encrypted database backups

---

## See Also

- [AUDIT_TRAIL.md](./AUDIT_TRAIL.md) - Audit logging documentation
- [TABLES_REFERENCE.md](./TABLES_REFERENCE.md) - Table schema details
- [SCHEMA_OVERVIEW.md](./SCHEMA_OVERVIEW.md) - Schema organization
- [/docs/operations/security/](../../operations/security/) - Security operations guide
