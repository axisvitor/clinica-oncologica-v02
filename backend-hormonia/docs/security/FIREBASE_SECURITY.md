# Firebase User Provisioning - Security Documentation

## 🔒 Security Overview

This document describes the comprehensive security measures implemented for Firebase user provisioning in the Hormonia Backend System.

## ⚠️ Critical Security Issue (RESOLVED)

**Previous Vulnerability:**
- Firebase user sync allowed ANY email domain, including public providers (gmail.com, yahoo.com, etc.)
- No validation of custom claims before user creation
- Potential security breach: anyone with Firebase account could gain system access

**Security Fix Implemented:**
- ✅ Domain whitelist enforced
- ✅ Public domains explicitly blocked
- ✅ Custom claims validation required
- ✅ Comprehensive audit logging
- ✅ Backward compatible with existing valid users

---

## 🛡️ Security Features

### 1. Domain Validation

**Only Authorized Domains Allowed:**
```
✅ neoplasiaslitoral.com
✅ clinica-oncologica.com.br
✅ hospital.local
```

**Public Domains Explicitly Blocked:**
```
❌ gmail.com
❌ yahoo.com
❌ hotmail.com
❌ outlook.com
❌ icloud.com
❌ All other public email providers
```

### 2. Custom Claims Validation

**Requirements:**
- Role MUST be present in Firebase custom claims
- Role MUST be one of: `admin`, `super_admin`, `doctor`, `medico`
- Validation occurs BEFORE user creation

**Example Valid Claims:**
```json
{
  "role": "doctor",
  "department": "oncology"
}
```

**Example Invalid Claims:**
```json
// ❌ Missing role
{}

// ❌ Invalid role
{
  "role": "patient"
}
```

### 3. Audit Logging

**All operations logged with details:**
- ✅ Successful user creation
- ⚠️ Rejected unauthorized domains
- ⚠️ Rejected invalid claims
- ❌ Failed operations

**Log Events:**
```python
{
  'event': 'firebase_user_provisioning',
  'type': 'rejected',  # or 'success', 'failed'
  'reason': 'unauthorized_domain',
  'firebase_uid': 'abc123...',
  'email': 'user@gmail.com',
  'error': 'Domain not in allowed list: gmail.com',
  'timestamp': '2025-09-30T10:30:00.000Z'
}
```

---

## 🔧 Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Firebase Security Configuration
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "clinica-oncologica.com.br", "hospital.local"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "super_admin", "doctor", "medico"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
```

### Configuration Defaults

```python
# app/config.py
FIREBASE_ALLOWED_DOMAINS: List[str] = Field(
    default=['neoplasiaslitoral.com', 'clinica-oncologica.com.br', 'hospital.local']
)
FIREBASE_REQUIRE_CUSTOM_CLAIMS: bool = Field(default=True)
FIREBASE_ALLOWED_ROLES: List[str] = Field(
    default=['admin', 'super_admin', 'doctor', 'medico']
)
FIREBASE_ENABLE_AUDIT_LOGGING: bool = Field(default=True)
FIREBASE_BLOCK_PUBLIC_DOMAINS: bool = Field(default=True)
```

---

## 🧪 Security Test Cases

### Test Case 1: Unauthorized Domain Rejection

**Scenario:** Attacker tries to create account with unauthorized domain

```python
firebase_data = {
    'email': 'attacker@unauthorized-domain.com',
    'custom_claims': {'role': 'admin'}
}

# Expected Result: ValueError raised
# Expected Log: 'rejected', 'unauthorized_domain'
```

### Test Case 2: Public Domain Blocking (gmail.com)

**Scenario:** User tries to sign up with gmail.com

```python
firebase_data = {
    'email': 'user@gmail.com',
    'custom_claims': {'role': 'doctor'}
}

# Expected Result: ValueError raised
# Expected Log: 'rejected', 'public_domain_blocked'
```

### Test Case 3: Missing Custom Claims

**Scenario:** Firebase user has no role in custom claims

```python
firebase_data = {
    'email': 'user@neoplasiaslitoral.com',
    'custom_claims': {}  # No role
}

# Expected Result: ValueError raised
# Expected Log: 'rejected', 'invalid_claims'
```

### Test Case 4: Invalid Role

**Scenario:** User has invalid role in claims

```python
firebase_data = {
    'email': 'user@neoplasiaslitoral.com',
    'custom_claims': {'role': 'patient'}  # Not allowed
}

# Expected Result: ValueError raised
# Expected Log: 'rejected', 'invalid_role'
```

### Test Case 5: Authorized Domain Success

**Scenario:** Valid user from authorized domain

```python
firebase_data = {
    'email': 'doctor@neoplasiaslitoral.com',
    'name': 'Dr. Smith',
    'custom_claims': {'role': 'doctor'},
    'email_verified': True
}

# Expected Result: User created successfully
# Expected Log: 'success', 'user_created'
```

---

## 🚨 Security Validation Flow

```
1. User authenticates with Firebase
   ↓
2. Backend receives Firebase JWT token
   ↓
3. SECURITY CHECK: Validate email domain
   ├─ ✅ Domain in allowed list? → Continue
   └─ ❌ Domain not allowed? → REJECT + LOG
   ↓
4. SECURITY CHECK: Validate custom claims
   ├─ ✅ Valid role present? → Continue
   └─ ❌ Missing/invalid role? → REJECT + LOG
   ↓
5. Check if user exists in database
   ├─ Found by Firebase UID → Update user
   ├─ Found by email → Link Firebase account
   └─ Not found → Create new user
   ↓
6. LOG SUCCESS + Return user
```

---

## 📊 Monitoring & Alerts

### Key Metrics to Monitor

1. **Rejected Attempts:**
   - Count of unauthorized domain attempts
   - Count of invalid claims attempts
   - Source IPs of rejected attempts

2. **Successful Provisioning:**
   - New users created per day
   - Domains distribution
   - Roles distribution

3. **Failed Operations:**
   - Database errors
   - Firebase API errors
   - Sync failures

### Log Analysis Queries

**Find Unauthorized Attempts (Last 24h):**
```sql
SELECT
  event_data->>'email' as email,
  event_data->>'reason' as reason,
  COUNT(*) as attempts
FROM audit_log_entries
WHERE event_type = 'firebase_user_provisioning'
  AND event_data->>'type' = 'rejected'
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY email, reason
ORDER BY attempts DESC;
```

**Find Successful Provisioning (Last 7 days):**
```sql
SELECT
  DATE(created_at) as date,
  COUNT(*) as users_created
FROM audit_log_entries
WHERE event_type = 'firebase_user_provisioning'
  AND event_data->>'type' = 'success'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## 🔐 Security Best Practices

### For System Administrators

1. **Review Audit Logs Daily:**
   - Check for unusual patterns
   - Monitor rejected attempts
   - Investigate repeated failures

2. **Keep Domain Whitelist Minimal:**
   - Only add domains you control
   - Never add public domains
   - Document each domain addition

3. **Validate Custom Claims:**
   - Ensure Firebase rules enforce claims
   - Regular audit of Firebase users
   - Remove users with invalid claims

4. **Monitor Firebase Console:**
   - Check for suspicious sign-ups
   - Verify custom claims are set
   - Review authentication logs

### For Developers

1. **Never Bypass Security Validation:**
   - Always use `sync_firebase_user()` method
   - Don't call `_create_user_from_firebase()` directly
   - Validate data before database operations

2. **Test Security Changes:**
   - Run full security test suite
   - Verify all edge cases
   - Test with production-like data

3. **Document Security Changes:**
   - Update this document
   - Add test cases
   - Update changelog

---

## 🐛 Troubleshooting

### User Cannot Sign In

**Symptom:** Valid user gets authentication error

**Possible Causes:**
1. Email domain not in whitelist
2. Missing custom claims in Firebase
3. Invalid role in custom claims

**Solution:**
1. Check domain: `echo "email@domain.com" | grep -E "(neoplasiaslitoral|clinica-oncologica|hospital\.local)"`
2. Verify Firebase claims in Firebase Console
3. Check audit logs for rejection reason

### Existing User Migration

**Scenario:** Need to migrate existing user to Firebase

**Steps:**
1. User should already exist in database
2. User signs in with Firebase
3. System automatically links Firebase UID
4. Verify user has valid custom claims

**Note:** Domain validation still applies during migration

---

## 📝 Changelog

### Version 2.0.0 (2025-09-30)

**SECURITY FIX: Critical Authorization Vulnerability**

**Changes:**
- ✅ Added domain whitelist validation
- ✅ Implemented public domain blocking
- ✅ Added custom claims validation
- ✅ Enhanced audit logging
- ✅ Removed gmail.com from authorized domains
- ✅ Added comprehensive test suite

**Migration Impact:**
- Existing valid users: ✅ No impact (backward compatible)
- New public domain users: ❌ Blocked (security fix)
- Invalid claims users: ❌ Blocked (security fix)

**Files Modified:**
- `app/config.py` - Added security configuration
- `app/services/firebase_user_sync_service.py` - Implemented validation
- `tests/test_firebase_security.py` - Added security tests

---

## 📞 Support

For security concerns or questions:

1. **Check Audit Logs:** Review logs for rejected attempts
2. **Run Tests:** `pytest tests/test_firebase_security.py -v`
3. **Review Configuration:** Verify `.env` settings
4. **Contact Security Team:** For critical issues

---

## ✅ Security Checklist

Before deploying to production:

- [ ] Environment variables configured correctly
- [ ] Domain whitelist contains ONLY authorized domains
- [ ] Public domains are NOT in whitelist
- [ ] Custom claims validation is enabled
- [ ] Audit logging is enabled
- [ ] All security tests pass
- [ ] Audit logs are monitored
- [ ] Backup/rollback plan ready
- [ ] Security team notified
- [ ] Documentation updated

---

**Last Updated:** 2025-09-30
**Security Level:** HIGH
**Status:** ✅ ACTIVE
