# Audit Trail Documentation

Comprehensive audit logging and compliance tracking for the Hormonia Backend system.

## Table of Contents

- [Audit Overview](#audit-overview)
- [Audit Log Tables](#audit-log-tables)
- [Event Types](#event-types)
- [Audit Patterns](#audit-patterns)
- [Compliance Requirements](#compliance-requirements)
- [Query Examples](#query-examples)
- [Retention Policies](#retention-policies)

---

## Audit Overview

### Purpose

The audit trail system tracks all security-sensitive operations, user activities, and system changes for:
- **Security monitoring** - Detect unauthorized access and suspicious activity
- **Compliance** - Meet HIPAA, LGPD, GDPR, SOC 2 requirements
- **Forensic analysis** - Investigate security incidents
- **User accountability** - Track who did what and when

### Audit Tables

| Table | Purpose | Retention |
|-------|---------|-----------|
| `audit_logs` | Security events (authentication, authorization) | 7 years (HIPAA) |
| `patient_onboarding_saga` | Transaction audit trail | Permanent |
| `user_sync_logs` | Firebase synchronization history | 1 year |
| `webhook_idempotency` | Webhook replay detection | 24 hours (auto-cleanup) |

---

## Audit Log Tables

### audit_logs

Primary security event tracking table.

**Schema:**
```sql
CREATE TABLE audit_logs (
  id                UUID PRIMARY KEY,
  event_type        audit_event_type NOT NULL,  -- Enum of event types
  event_status      VARCHAR(50) DEFAULT 'success',
  user_id           UUID,  -- Nullable (failed logins)
  user_email        VARCHAR(255),
  firebase_uid      VARCHAR(255),
  ip_address        INET,
  user_agent        TEXT,
  resource          VARCHAR(255),  -- Endpoint or resource
  action            VARCHAR(255),  -- Action performed
  event_metadata    JSONB NOT NULL DEFAULT '{}',
  message           TEXT,
  error_details     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Indexes:**
```sql
-- Performance indexes
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_ip_address ON audit_logs(ip_address);

-- Composite indexes for common queries
CREATE INDEX idx_audit_user_event_time ON audit_logs(user_id, event_type, created_at);
CREATE INDEX idx_audit_ip_time ON audit_logs(ip_address, created_at);
CREATE INDEX idx_audit_event_status_time ON audit_logs(event_type, event_status, created_at);
CREATE INDEX idx_audit_firebase_time ON audit_logs(firebase_uid, created_at);
CREATE INDEX idx_audit_email_time ON audit_logs(user_email, created_at);
```

---

## Event Types

### Authentication Events

```python
class AuditEventType(enum.Enum):
    # Login/Logout
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"

    # Session Management
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_INVALIDATED = "session_invalidated"
    TOKEN_REFRESH = "token_refresh"
```

**Example Audit Entry:**
```json
{
  "event_type": "login_success",
  "event_status": "success",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_email": "doctor@example.com",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "resource": "/api/v2/auth/login",
  "action": "authenticate",
  "event_metadata": {
    "device_type": "desktop",
    "location": {"city": "São Paulo", "country": "Brazil"},
    "mfa_used": false
  },
  "message": "User logged in successfully",
  "created_at": "2025-11-15T12:00:00Z"
}
```

### Authorization Events

```python
# Access Control
ACCESS_DENIED = "access_denied"
PERMISSION_CHANGED = "permission_changed"
ROLE_CHANGED = "role_changed"
```

**Example Audit Entry:**
```json
{
  "event_type": "access_denied",
  "event_status": "failure",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "resource": "/api/v2/admin/users",
  "action": "list_users",
  "event_metadata": {
    "required_role": "admin",
    "user_role": "doctor"
  },
  "message": "User attempted to access admin endpoint without permission"
}
```

### Account Management Events

```python
# Password Management
PASSWORD_CHANGED = "password_changed"
PASSWORD_RESET_REQUESTED = "password_reset_requested"
PASSWORD_RESET_COMPLETED = "password_reset_completed"

# Account Status
ACCOUNT_LOCKED = "account_locked"
ACCOUNT_UNLOCKED = "account_unlocked"
ACCOUNT_DISABLED = "account_disabled"
ACCOUNT_ENABLED = "account_enabled"

# Profile Changes
PROFILE_UPDATED = "profile_updated"
EMAIL_CHANGED = "email_changed"
```

### Security Events

```python
# Security Violations
SUSPICIOUS_ACTIVITY = "suspicious_activity"
RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
INVALID_TOKEN = "invalid_token"
CSRF_VIOLATION = "csrf_violation"
```

**Example Suspicious Activity:**
```json
{
  "event_type": "suspicious_activity",
  "event_status": "error",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "ip_address": "192.168.1.200",
  "event_metadata": {
    "reason": "ip_mismatch",
    "expected_ip": "192.168.1.100",
    "actual_ip": "192.168.1.200",
    "session_id": "session_123",
    "risk_score": "high"
  },
  "message": "Session IP address changed suspiciously"
}
```

---

## Audit Patterns

### Audit on Authentication

**Successful Login:**
```python
def login(email: str, password: str):
    user = authenticate(email, password)

    if user:
        # Create audit log
        audit_log = AuditLog(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_status="success",
            user_id=user.id,
            user_email=user.email,
            firebase_uid=user.firebase_uid,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            resource=request.path,
            action="authenticate",
            event_metadata={
                "device_type": detect_device_type(),
                "location": get_geolocation()
            },
            message="User logged in successfully"
        )
        db.add(audit_log)

        return create_session(user)
```

**Failed Login:**
```python
def login(email: str, password: str):
    user = get_user_by_email(email)

    if not user or not verify_password(user, password):
        # Audit failed login attempt
        audit_log = AuditLog(
            event_type=AuditEventType.LOGIN_FAILURE,
            event_status="failure",
            user_id=user.id if user else None,
            user_email=email,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            resource=request.path,
            action="authenticate",
            event_metadata={
                "reason": "invalid_credentials",
                "attempts": get_failed_attempts(email) + 1
            },
            message="Invalid email or password",
            error_details="Authentication failed"
        )
        db.add(audit_log)

        # Increment failed attempts
        increment_failed_attempts(email)
```

### Audit on Authorization

```python
@require_auth
@require_role(UserRole.ADMIN)
def admin_endpoint():
    if current_user.role != UserRole.ADMIN:
        # Audit access denial
        audit_log = AuditLog(
            event_type=AuditEventType.ACCESS_DENIED,
            event_status="failure",
            user_id=current_user.id,
            user_email=current_user.email,
            ip_address=request.remote_addr,
            resource=request.path,
            action=request.method,
            event_metadata={
                "required_role": "admin",
                "user_role": current_user.role.value
            },
            message=f"User {current_user.email} attempted to access admin endpoint"
        )
        db.add(audit_log)

        raise HTTPException(403, "Forbidden")
```

### Audit on Data Changes

```python
def update_patient(patient_id: UUID, data: dict):
    patient = get_patient(patient_id)

    # Track changes
    changes = {}
    for key, value in data.items():
        if getattr(patient, key) != value:
            changes[key] = {
                "old": getattr(patient, key),
                "new": value
            }

    # Update patient
    for key, value in data.items():
        setattr(patient, key, value)

    # Audit data modification
    audit_log = AuditLog(
        event_type=AuditEventType.PROFILE_UPDATED,
        event_status="success",
        user_id=current_user.id,
        resource=f"/patients/{patient_id}",
        action="update",
        event_metadata={
            "patient_id": str(patient_id),
            "changes": changes
        },
        message=f"Patient {patient_id} updated by {current_user.email}"
    )
    db.add(audit_log)
```

---

## Compliance Requirements

### HIPAA Compliance

**Required Audit Events:**
- ✅ User login/logout (authentication)
- ✅ Access to PHI (patient data)
- ✅ PHI modifications (create, update, delete)
- ✅ Failed access attempts
- ✅ System configuration changes
- ✅ Security incidents

**Audit Log Requirements:**
- **Who**: User ID, email
- **What**: Action performed, resource accessed
- **When**: Timestamp (timezone-aware)
- **Where**: IP address, location
- **Why**: Context in event_metadata
- **Result**: Success or failure

**Retention:**
- Minimum 6 years (HIPAA requirement)
- Immutable logs (no updates or deletes)

### LGPD/GDPR Compliance

**Data Subject Rights Audit:**
```python
# Right to access (export data)
audit_log = AuditLog(
    event_type="data_export_requested",
    user_id=patient.doctor_id,
    event_metadata={
        "patient_id": str(patient.id),
        "export_format": "json",
        "data_types": ["profile", "medical_history", "quiz_responses"]
    }
)

# Right to erasure (delete data)
audit_log = AuditLog(
    event_type="data_deletion_requested",
    user_id=patient.doctor_id,
    event_metadata={
        "patient_id": str(patient.id),
        "deletion_reason": "patient_request",
        "deletion_type": "soft_delete"
    }
)
```

### SOC 2 Compliance

**Security Controls:**
- Audit all privileged access
- Track system configuration changes
- Monitor failed authentication attempts
- Log security violations

---

## Query Examples

### Security Monitoring

**Failed Login Attempts (Last 24 Hours):**
```sql
SELECT
  user_email,
  ip_address,
  COUNT(*) as attempts,
  MAX(created_at) as last_attempt
FROM audit_logs
WHERE event_type = 'login_failure'
AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY user_email, ip_address
ORDER BY attempts DESC;
```

**Successful Logins by User:**
```sql
SELECT
  user_email,
  COUNT(*) as login_count,
  MIN(created_at) as first_login,
  MAX(created_at) as last_login
FROM audit_logs
WHERE event_type = 'login_success'
AND user_id = '123e4567-e89b-12d3-a456-426614174000'
AND created_at > NOW() - INTERVAL '30 days'
GROUP BY user_email;
```

**Access Denied Events:**
```sql
SELECT
  user_email,
  resource,
  event_metadata->>'required_role' as required_role,
  event_metadata->>'user_role' as user_role,
  created_at
FROM audit_logs
WHERE event_type = 'access_denied'
ORDER BY created_at DESC
LIMIT 100;
```

**Suspicious Activity:**
```sql
SELECT
  user_email,
  ip_address,
  event_metadata->>'reason' as reason,
  event_metadata->>'risk_score' as risk_score,
  created_at
FROM audit_logs
WHERE event_type = 'suspicious_activity'
ORDER BY created_at DESC;
```

### User Activity Timeline

```sql
SELECT
  event_type,
  resource,
  action,
  event_status,
  ip_address,
  created_at
FROM audit_logs
WHERE user_id = '123e4567-e89b-12d3-a456-426614174000'
ORDER BY created_at DESC
LIMIT 50;
```

### PHI Access Audit

```sql
-- Track who accessed patient data
SELECT
  a.user_email,
  a.resource,
  a.action,
  a.event_metadata->>'patient_id' as patient_id,
  a.created_at
FROM audit_logs a
WHERE a.resource LIKE '/api/v2/patients/%'
AND a.event_status = 'success'
ORDER BY a.created_at DESC;
```

---

## Retention Policies

### Audit Log Retention

**Production:**
```sql
-- Retention: 7 years (HIPAA requirement)
DELETE FROM audit_logs
WHERE created_at < NOW() - INTERVAL '7 years';
```

**Archive Strategy:**
```sql
-- Create archive table
CREATE TABLE audit_logs_archive (LIKE audit_logs INCLUDING ALL);

-- Archive old logs (before deletion)
INSERT INTO audit_logs_archive
SELECT * FROM audit_logs
WHERE created_at < NOW() - INTERVAL '7 years';

-- Delete archived logs from main table
DELETE FROM audit_logs
WHERE created_at < NOW() - INTERVAL '7 years';
```

**Backup:**
- Daily backups to S3/Cloud Storage
- Encrypted at rest
- Immutable backups (write-once-read-many)

### Webhook Idempotency Cleanup

**Auto-cleanup:**
```sql
-- Delete expired webhook events (TTL: 24 hours)
DELETE FROM webhook_idempotency
WHERE expires_at < NOW();
```

**Scheduled Job:**
```python
# Run every hour
@celery_app.task
def cleanup_expired_webhooks():
    db.execute("""
        DELETE FROM webhook_idempotency
        WHERE expires_at < NOW()
    """)
    db.commit()
```

---

## Audit Best Practices

### 1. Immutability

**Never modify or delete audit logs:**
```python
# ❌ Bad: Update audit log
audit_log.message = "Updated message"

# ✅ Good: Create new audit entry
new_audit_log = AuditLog(
    event_type="audit_log_correction",
    event_metadata={
        "original_log_id": audit_log.id,
        "correction": "Updated message"
    }
)
```

### 2. Complete Context

**Include all relevant information:**
```python
audit_log = AuditLog(
    event_type=...,
    user_id=current_user.id,
    user_email=current_user.email,
    firebase_uid=current_user.firebase_uid,
    ip_address=request.remote_addr,
    user_agent=request.headers.get('User-Agent'),
    resource=request.path,
    action=request.method,
    event_metadata={
        "request_id": request.id,
        "session_id": session.id,
        "device_type": detect_device(),
        "location": get_geolocation(),
        # Include any relevant context
    }
)
```

### 3. Consistent Format

**Use standard event types and metadata:**
```python
# ✅ Good: Standard event type
event_type = AuditEventType.LOGIN_SUCCESS

# ❌ Bad: Custom string
event_type = "user_logged_in_successfully"
```

### 4. Performance

**Batch audit logs for high-volume operations:**
```python
audit_logs = []

for patient in patients:
    # Process patient
    ...

    # Create audit log
    audit_logs.append(AuditLog(...))

# Bulk insert
db.bulk_save_objects(audit_logs)
db.commit()
```

---

## See Also

- [SECURITY.md](./SECURITY.md) - Security architecture and RBAC
- [TABLES_REFERENCE.md](./TABLES_REFERENCE.md) - Table schema details
- [SCHEMA_OVERVIEW.md](./SCHEMA_OVERVIEW.md) - Schema organization
- [/docs/operations/security/](../../operations/security/) - Security operations guide
