# Audit Logging Implementation Report

## Executive Summary

Comprehensive audit logging has been implemented across all template management routes to track CRUD operations, ensure compliance, and facilitate debugging. This implementation provides full visibility into who performed what action, when, and from where.

## Implementation Overview

### 1. Audit Logger Utility (`app/utils/audit_logger.py`)

**Location:** `/backend-hormonia/app/utils/audit_logger.py`

**Features:**
- Structured JSON logging for easy parsing and analysis
- Support for 10 different audit actions
- Automatic timestamp generation with timezone support
- IP address tracking for security
- Success/failure tracking with error messages
- Batch operation logging
- Security event logging

**Audit Actions:**
```python
class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    PUBLISH = "publish"
    ARCHIVE = "archive"
    DUPLICATE = "duplicate"
    ROLLBACK = "rollback"
    SEARCH = "search"
    VALIDATE = "validate"
```

### 2. Integration Points

#### Flow Templates (`app/api/v2/routers/flow_templates.py`)

**Audited Operations:**
1. **Create Template** (POST `/flows`)
   - Logs template creation with name, version, kind, and draft status
   - Captures user ID, role, and IP address

2. **Update Template** (PUT `/flows/{template_id}`)
   - Tracks all field changes
   - Records what was modified (template_name, is_active, is_draft)

3. **Delete/Archive Template** (DELETE `/flows/{template_id}`)
   - Distinguishes between soft delete (archive) and hard delete
   - Preserves template name for audit trail

4. **Duplicate Template** (POST `/flows/{template_id}/duplicate`)
   - Links source template to new template
   - Records new version and name

5. **Create Flow Kind** (POST `/flow-kinds`)
   - Tracks new flow kind creation
   - Records kind_key and display_name

#### Quiz Templates (`app/api/v2/routers/quiz_templates.py`)

**Audited Operations:**
1. **Create Quiz Template** (POST `/quizzes`)
   - Logs template name, version, and category

2. **Update Quiz Template** (PUT `/quizzes/{template_id}`)
   - Tracks changes to name, is_active, category

3. **Delete Quiz Template** (DELETE `/quizzes/{template_id}`)
   - Records hard deletion with template name

4. **Duplicate Quiz Template** (POST `/quizzes/{template_id}/duplicate`)
   - Links source to duplicate with new name and version

#### Template Versions (`app/api/v2/routers/template_versions.py`)

**Audited Operations:**
1. **Rollback Version** (POST `/flows/{template_id}/rollback`)
   - Records source version and new version numbers
   - Captures rollback reason and active status

2. **Publish Version** (POST `/flows/{template_id}/publish`)
   - Tracks template publication
   - Records whether set as active version

#### Template Admin (`app/api/v2/routers/template_admin.py`)

**Audited Operations:**
1. **Search Templates** (GET `/search`)
   - Logs search queries and result counts
   - Tracks search patterns for analytics

2. **Validate Template** (POST `/validate`)
   - Records validation attempts
   - Captures validation results (errors/warnings count)

## Audit Log Structure

### Standard Log Entry
```json
{
  "timestamp": "2025-12-22T19:30:00.000Z",
  "action": "create",
  "resource_type": "flow_template",
  "resource_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "user-uuid-123",
  "user_role": "admin",
  "details": {
    "template_name": "Patient Onboarding Flow",
    "version_number": 1,
    "kind_key": "onboarding",
    "is_draft": true
  },
  "ip_address": "192.168.1.100",
  "success": true,
  "error_message": null
}
```

### Batch Operation Log Entry
```json
{
  "timestamp": "2025-12-22T19:30:00.000Z",
  "action": "archive",
  "resource_type": "flow_template",
  "resource_ids": ["id-1", "id-2", "id-3"],
  "resource_count": 3,
  "user_id": "user-uuid-123",
  "user_role": "admin",
  "details": {
    "reason": "End of quarter cleanup"
  },
  "ip_address": "192.168.1.100",
  "success": true
}
```

### Security Event Log Entry
```json
{
  "timestamp": "2025-12-22T19:30:00.000Z",
  "event_type": "permission_denied",
  "user_id": "user-uuid-123",
  "details": {
    "attempted_action": "delete",
    "resource": "template-456"
  },
  "ip_address": "192.168.1.100",
  "severity": "high"
}
```

## Usage Examples

### Creating a Template
```python
AuditLogger.log(
    action=AuditAction.CREATE,
    resource_type="flow_template",
    resource_id=str(template_version.id),
    user_id=str(user_uuid),
    user_role=role,
    details={
        "template_name": template_version.template_name,
        "version_number": template_version.version_number,
        "kind_key": flow_kind.kind_key,
        "is_draft": template_version.is_draft,
    },
    ip_address=request.client.host if request.client else None,
)
```

### Updating a Template
```python
changes = {}
if updates.template_name is not None:
    changes["template_name"] = updates.template_name
if updates.is_active is not None:
    changes["is_active"] = updates.is_active

AuditLogger.log(
    action=AuditAction.UPDATE,
    resource_type="flow_template",
    resource_id=str(template_id),
    user_id=str(user_uuid),
    user_role=role,
    details={"changes": changes},
    ip_address=request.client.host if request.client else None,
)
```

### Security Event
```python
AuditLogger.log_security_event(
    event_type="permission_denied",
    user_id="user-uuid",
    details={"attempted_action": "delete", "resource": "template-123"},
    ip_address="192.168.1.1",
    severity="high"
)
```

## Benefits

### 1. Compliance
- **HIPAA Compliance**: Full audit trail of all template modifications
- **SOC 2**: Comprehensive logging for security audits
- **GDPR**: Tracks data access and modifications

### 2. Security
- **Intrusion Detection**: IP tracking helps identify suspicious activity
- **Access Patterns**: Search and validation logs reveal usage patterns
- **Permission Violations**: Security events log unauthorized attempts

### 3. Debugging
- **Error Tracking**: Failed operations logged with error messages
- **Change History**: Full history of what changed and when
- **User Actions**: Track down who made specific changes

### 4. Analytics
- **Usage Patterns**: Search queries and validation attempts
- **Popular Operations**: Frequency of creates vs. updates vs. deletes
- **Performance**: Identify slow or problematic operations

## Testing

### Unit Tests (`tests/utils/test_audit_logger.py`)

**Test Coverage:**
- Basic audit log entry creation
- Logging with additional details
- IP address tracking
- Failed operation logging
- Batch operation logging
- Access logging for sensitive resources
- Security event logging
- All audit action types
- Timestamp format validation

**Run Tests:**
```bash
cd backend-hormonia
pytest tests/utils/test_audit_logger.py -v
```

## Log Analysis

### Query Audit Logs

Using standard log aggregation tools (ELK, Splunk, CloudWatch):

**Find all template creations by a user:**
```
audit_data.action:"create" AND audit_data.user_id:"user-123"
```

**Find all failed operations:**
```
audit_data.success:false
```

**Find all deletions in last 24 hours:**
```
audit_data.action:"delete" AND audit_data.timestamp:[now-24h TO now]
```

**Find security events:**
```
security_event.severity:"high" OR security_event.severity:"critical"
```

## Best Practices

### 1. Always Log Actions
- Log all CRUD operations immediately after database commit
- Include success/failure status
- Capture error messages for failures

### 2. Include Context
- User ID and role
- IP address when available
- Resource details (name, version, etc.)
- Operation-specific metadata

### 3. Security Considerations
- Never log sensitive data (passwords, PII)
- Use resource IDs, not full data
- Log security events separately
- Set appropriate severity levels

### 4. Performance
- Audit logging is non-blocking
- Uses structured logging for efficiency
- Minimal performance overhead

## Future Enhancements

### 1. Centralized Log Storage
- Integrate with ELK stack or CloudWatch
- Real-time log streaming
- Long-term retention policies

### 2. Alerting
- Real-time alerts for security events
- Suspicious activity detection
- Failed operation notifications

### 3. Audit UI
- Web interface for audit log viewing
- Search and filter capabilities
- Export to CSV/PDF

### 4. Compliance Reports
- Automated compliance report generation
- User activity summaries
- Resource change histories

## Files Modified

1. **Created:**
   - `/backend-hormonia/app/utils/audit_logger.py` (211 lines)
   - `/backend-hormonia/tests/utils/test_audit_logger.py` (209 lines)
   - `/docs/AUDIT_LOGGING_IMPLEMENTATION.md` (this file)

2. **Modified:**
   - `/backend-hormonia/app/api/v2/routers/flow_templates.py`
   - `/backend-hormonia/app/api/v2/routers/quiz_templates.py`
   - `/backend-hormonia/app/api/v2/routers/template_versions.py`
   - `/backend-hormonia/app/api/v2/routers/template_admin.py`

## Conclusion

The audit logging implementation provides comprehensive visibility into all template operations, meeting compliance requirements while facilitating debugging and security monitoring. The structured JSON format enables easy integration with log analysis tools, and the modular design allows for future enhancements without disrupting existing functionality.

All template CRUD operations are now fully audited with:
- User identification and role tracking
- IP address for security
- Detailed operation context
- Success/failure status
- Timestamp with timezone
- Action-specific metadata

The implementation is production-ready, well-tested, and follows best practices for audit logging in healthcare applications.
