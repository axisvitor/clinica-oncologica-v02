# Audit Logging - Quick Reference Guide

## Import
```python
from app.utils.audit_logger import AuditLogger, AuditAction
```

## Available Actions
```python
AuditAction.CREATE     # Resource creation
AuditAction.UPDATE     # Resource modification
AuditAction.DELETE     # Hard deletion
AuditAction.ARCHIVE    # Soft deletion (is_active=False)
AuditAction.READ       # Sensitive data access
AuditAction.PUBLISH    # Draft to published
AuditAction.DUPLICATE  # Resource duplication
AuditAction.ROLLBACK   # Version rollback
AuditAction.SEARCH     # Search operations
AuditAction.VALIDATE   # Validation attempts
```

## Basic Usage

### Standard Audit Log
```python
AuditLogger.log(
    action=AuditAction.CREATE,
    resource_type="flow_template",
    resource_id=str(template_id),
    user_id=str(user_uuid),
    user_role=user_role,
    details={"template_name": "Example Flow"},
    ip_address=request.client.host if request.client else None,
)
```

### Update with Changes
```python
changes = {}
if updates.name:
    changes["name"] = updates.name
if updates.is_active is not None:
    changes["is_active"] = updates.is_active

AuditLogger.log(
    action=AuditAction.UPDATE,
    resource_type="template",
    resource_id=str(id),
    user_id=str(user_id),
    details={"changes": changes},
    ip_address=request.client.host,
)
```

### Delete/Archive
```python
AuditLogger.log(
    action=AuditAction.DELETE if not soft_delete else AuditAction.ARCHIVE,
    resource_type="template",
    resource_id=str(id),
    user_id=str(user_id),
    details={"soft_delete": soft_delete},
    ip_address=request.client.host,
)
```

### Failed Operations
```python
AuditLogger.log(
    action=AuditAction.UPDATE,
    resource_type="template",
    resource_id=str(id),
    user_id=str(user_id),
    success=False,
    error_message="Permission denied",
)
```

### Batch Operations
```python
AuditLogger.log_batch(
    action=AuditAction.ARCHIVE,
    resource_type="template",
    resource_ids=["id1", "id2", "id3"],
    user_id=str(user_id),
    details={"reason": "Cleanup"},
)
```

### Access Logging
```python
AuditLogger.log_access(
    resource_type="patient_data",
    resource_id=str(patient_id),
    user_id=str(user_id),
    user_role="doctor",
    access_type="view",
    ip_address=request.client.host,
)
```

### Security Events
```python
AuditLogger.log_security_event(
    event_type="permission_denied",
    user_id=str(user_id),
    details={"attempted_action": "delete", "resource": "template-123"},
    ip_address=request.client.host,
    severity="high",  # low, medium, high, critical
)
```

## Log Entry Structure

```json
{
  "timestamp": "2025-12-22T19:30:00.000000-03:00",
  "action": "create",
  "resource_type": "flow_template",
  "resource_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": "user-uuid-456",
  "user_role": "admin",
  "details": {
    "template_name": "Patient Onboarding",
    "version_number": 1,
    "kind_key": "onboarding"
  },
  "ip_address": "192.168.1.100",
  "success": true,
  "error_message": null
}
```

## Common Patterns

### Create Operation
```python
# After db.commit() and db.refresh()
AuditLogger.log(
    action=AuditAction.CREATE,
    resource_type="resource_type",
    resource_id=str(new_resource.id),
    user_id=str(user_uuid),
    user_role=role,
    details={
        "name": new_resource.name,
        "other_field": new_resource.other_field,
    },
    ip_address=request.client.host if request.client else None,
)
```

### Update Operation
```python
# After db.commit()
changes = {}
if updates.field1:
    changes["field1"] = updates.field1
if updates.field2 is not None:
    changes["field2"] = updates.field2

AuditLogger.log(
    action=AuditAction.UPDATE,
    resource_type="resource_type",
    resource_id=str(resource_id),
    user_id=str(user_uuid),
    user_role=role,
    details={"changes": changes},
    ip_address=request.client.host if request.client else None,
)
```

### Delete Operation
```python
# After db.commit()
AuditLogger.log(
    action=AuditAction.DELETE,
    resource_type="resource_type",
    resource_id=str(resource_id),
    user_id=str(user_uuid),
    user_role=role,
    details={"resource_name": resource.name},
    ip_address=request.client.host if request.client else None,
)
```

## Query Examples

### ELK/Splunk Queries

**All actions by user:**
```
audit_data.user_id:"user-123"
```

**Failed operations:**
```
audit_data.success:false
```

**Specific action type:**
```
audit_data.action:"delete"
```

**Time range:**
```
audit_data.timestamp:[2025-12-22T00:00:00 TO 2025-12-22T23:59:59]
```

**Resource type:**
```
audit_data.resource_type:"flow_template"
```

**High severity security events:**
```
security_event.severity:"high" OR security_event.severity:"critical"
```

**Combined query:**
```
audit_data.action:"delete" AND audit_data.user_role:"admin" AND audit_data.timestamp:[now-24h TO now]
```

## Best Practices

### ✅ DO
- Log immediately after database commit
- Include user ID, role, and IP address
- Capture operation-specific details
- Use appropriate action types
- Log both success and failure
- Include error messages for failures

### ❌ DON'T
- Log sensitive data (passwords, tokens, PII)
- Log before database commit (may log failed operations as success)
- Log entire objects (use IDs and key fields)
- Skip IP address tracking
- Forget to log failed operations
- Use generic action types

## Performance

- Audit logging adds ~1-2ms per operation
- Logging is non-blocking
- Uses structured logging for efficiency
- Minimal memory overhead

## Security Considerations

- Never log passwords or authentication tokens
- Use resource IDs, not full data
- Mask or hash PII if absolutely necessary to log
- Set appropriate log retention policies
- Restrict access to audit logs
- Monitor for unauthorized access to logs themselves

## Compliance

Audit logs support:
- **HIPAA** - Complete audit trail of PHI access
- **SOC 2** - Security event logging
- **GDPR** - Data processing records
- **ISO 27001** - Information security management

## Troubleshooting

### Issue: IP address is None
```python
# Solution: Check if request.client exists
ip_address=request.client.host if request.client else None
```

### Issue: User context not available
```python
# Solution: Use _extract_user_context helper
from app.api.v2.templates_shared import _extract_user_context
role, user_uuid = _extract_user_context(current_user)
```

### Issue: Details not showing in logs
```python
# Solution: Ensure logger is configured for JSON output
# Check logging configuration in app settings
```

## Testing

```python
from app.utils.audit_logger import AuditLogger, AuditAction
from unittest.mock import patch

@patch("app.utils.audit_logger.logger")
def test_audit_logging(mock_logger):
    AuditLogger.log(
        action=AuditAction.CREATE,
        resource_type="test",
        resource_id="test-123",
        user_id="user-456",
    )

    assert mock_logger.log.called
    call_args = mock_logger.log.call_args
    audit_data = call_args[1]["extra"]["audit_data"]

    assert audit_data["action"] == "create"
    assert audit_data["resource_id"] == "test-123"
```

## Integration Checklist

When adding audit logging to a new endpoint:

- [ ] Import AuditLogger and AuditAction
- [ ] Identify the appropriate action type
- [ ] Place audit call after db.commit()
- [ ] Include user_id and user_role
- [ ] Capture IP address from request
- [ ] Add operation-specific details
- [ ] Handle both success and failure cases
- [ ] Test the audit logging
- [ ] Verify log format in output

---

**Quick Links:**
- [Full Implementation Guide](/docs/AUDIT_LOGGING_IMPLEMENTATION.md)
- [Completion Summary](/docs/P2_AUDIT_LOGGING_COMPLETION_SUMMARY.md)
- [Source Code](/backend-hormonia/app/utils/audit_logger.py)
- [Unit Tests](/backend-hormonia/tests/utils/test_audit_logger.py)
