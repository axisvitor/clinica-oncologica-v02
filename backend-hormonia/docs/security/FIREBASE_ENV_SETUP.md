# Firebase Security Configuration Guide

## 🚀 Quick Setup

This guide shows how to configure Firebase security settings for the Hormonia Backend System.

---

## 📋 Environment Variables

### Required Variables

Add these to your `.env` file:

```bash
# ============================================================================
# FIREBASE SECURITY CONFIGURATION
# ============================================================================

# Authorized email domains (JSON array format)
# ONLY domains you control should be listed here
# ❌ NEVER add public domains (gmail.com, yahoo.com, etc.)
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "clinica-oncologica.com.br", "hospital.local"]

# Require custom claims before user creation
# Set to 'false' only for testing (NOT recommended for production)
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true

# Allowed roles in Firebase custom claims
# Users MUST have one of these roles to be created
FIREBASE_ALLOWED_ROLES=["admin", "super_admin", "doctor", "medico"]

# Enable comprehensive audit logging
# Set to 'false' to disable logging (NOT recommended)
FIREBASE_ENABLE_AUDIT_LOGGING=true

# Block public email domains
# Set to 'false' to allow public domains (DANGEROUS - NOT recommended)
FIREBASE_BLOCK_PUBLIC_DOMAINS=true

# Public domains blocklist (JSON array format)
# These domains are explicitly blocked even if in allowed list
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
```

---

## 🎯 Configuration Scenarios

### Scenario 1: Production Environment (Recommended)

```bash
# Strict security - only organization domains
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "clinica-oncologica.com.br"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "doctor"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
```

**Use Case:**
- ✅ Production deployments
- ✅ High security requirements
- ✅ Organization-only access

### Scenario 2: Development Environment

```bash
# Relaxed for local testing with test domain
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "hospital.local", "test.local"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "doctor", "medico"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com"]
```

**Use Case:**
- ✅ Local development
- ✅ Testing with fake domains
- ⚠️ NOT for production

### Scenario 3: Testing Environment (Use with Caution)

```bash
# Minimal restrictions for automated testing
FIREBASE_ALLOWED_DOMAINS=["test.local", "example.com"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=false
FIREBASE_ALLOWED_ROLES=["admin", "doctor", "test"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com"]
```

**Use Case:**
- ✅ CI/CD pipelines
- ✅ Automated tests
- ❌ NEVER use in production

---

## ⚙️ Configuration Formats

### JSON Array Format (Recommended)

```bash
# Use JSON array for multiple values
FIREBASE_ALLOWED_DOMAINS=["domain1.com", "domain2.com", "domain3.com"]
FIREBASE_ALLOWED_ROLES=["admin", "doctor", "medico"]
```

### Comma-Separated Format (Alternative)

```bash
# Alternative format (comma-separated)
FIREBASE_ALLOWED_DOMAINS=domain1.com,domain2.com,domain3.com
FIREBASE_ALLOWED_ROLES=admin,doctor,medico
```

### Single Value Format

```bash
# For single domain (rare)
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
```

---

## 🔍 Validation Rules

### Domain Validation

**Valid Domains:**
```bash
✅ neoplasiaslitoral.com
✅ clinica-oncologica.com.br
✅ hospital.local
✅ subdomain.example.com
```

**Invalid Domains:**
```bash
❌ gmail.com (public domain)
❌ yahoo.com (public domain)
❌ @neoplasiaslitoral.com (includes @)
❌ neoplasiaslitoral (missing TLD)
```

### Role Validation

**Valid Roles:**
```bash
✅ admin
✅ super_admin
✅ doctor
✅ medico
```

**Invalid Roles:**
```bash
❌ patient (not authorized)
❌ user (not authorized)
❌ guest (not authorized)
```

---

## 🧪 Testing Configuration

### Test Your Configuration

Create a test script `scripts/test_firebase_config.py`:

```python
from app.config import get_firebase_security_config

def test_config():
    config = get_firebase_security_config()

    print("Firebase Security Configuration:")
    print(f"  Allowed Domains: {config['allowed_domains']}")
    print(f"  Require Claims: {config['require_custom_claims']}")
    print(f"  Allowed Roles: {config['allowed_roles']}")
    print(f"  Audit Logging: {config['enable_audit_logging']}")
    print(f"  Block Public: {config['block_public_domains']}")
    print(f"  Blocklist: {config['public_domains_blocklist']}")

    # Validate configuration
    assert 'gmail.com' not in config['allowed_domains'], "❌ SECURITY ERROR: gmail.com in allowed list!"
    assert 'yahoo.com' not in config['allowed_domains'], "❌ SECURITY ERROR: yahoo.com in allowed list!"
    assert config['require_custom_claims'] is True, "⚠️ WARNING: Custom claims not required!"
    assert config['block_public_domains'] is True, "⚠️ WARNING: Public domains not blocked!"

    print("\n✅ Configuration validated successfully!")

if __name__ == "__main__":
    test_config()
```

**Run Test:**
```bash
cd Backend
python scripts/test_firebase_config.py
```

---

## 🔒 Security Checklist

Before deploying:

- [ ] `.env` file configured with correct domains
- [ ] Public domains NOT in `FIREBASE_ALLOWED_DOMAINS`
- [ ] `FIREBASE_REQUIRE_CUSTOM_CLAIMS=true` in production
- [ ] `FIREBASE_BLOCK_PUBLIC_DOMAINS=true` in production
- [ ] `FIREBASE_ENABLE_AUDIT_LOGGING=true` always
- [ ] Configuration tested with test script
- [ ] Security tests pass: `pytest tests/test_firebase_security.py`

---

## 🚨 Common Mistakes

### Mistake 1: Including Public Domains

```bash
# ❌ WRONG - SECURITY VULNERABILITY
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "gmail.com"]
```

**Why Wrong:** Anyone with Gmail account can create user

**Fix:**
```bash
# ✅ CORRECT
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
```

### Mistake 2: Disabling Claims Validation

```bash
# ❌ WRONG - SECURITY RISK
FIREBASE_REQUIRE_CUSTOM_CLAIMS=false
```

**Why Wrong:** Users without roles can be created

**Fix:**
```bash
# ✅ CORRECT
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
```

### Mistake 3: Disabling Public Domain Blocking

```bash
# ❌ WRONG - BYPASSES SECURITY
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
```

**Why Wrong:** Public domains could be added to allowed list

**Fix:**
```bash
# ✅ CORRECT
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

---

## 📊 Environment-Specific Settings

### Development (.env.development)

```bash
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "hospital.local"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "doctor", "medico"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

### Production (.env.production)

```bash
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "clinica-oncologica.com.br"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "doctor"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
FIREBASE_PUBLIC_DOMAINS_BLOCKLIST=["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "protonmail.com"]
```

### Staging (.env.staging)

```bash
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "staging.hospital.local"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin", "doctor", "medico"]
FIREBASE_ENABLE_AUDIT_LOGGING=true
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

---

## 🔄 Migration from Old Configuration

### If You Had gmail.com Previously

**Old Configuration:**
```bash
# In firebase_user_sync_service.py
AUTHORIZED_DOMAINS = [
    'neoplasiaslitoral.com',
    'hospital.local',
    'gmail.com'  # For testing only - remove in production
]
```

**New Configuration:**
```bash
# In .env file
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com", "hospital.local"]
# gmail.com is automatically blocked by FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

**Action Required:**
1. Remove gmail.com from allowed list
2. Set `FIREBASE_BLOCK_PUBLIC_DOMAINS=true`
3. Run security tests to verify
4. Monitor audit logs for rejected attempts

---

## 🛠️ Troubleshooting

### Problem: Configuration Not Loading

**Symptom:** Default values used instead of .env values

**Solutions:**
1. Check .env file exists in Backend directory
2. Verify environment variable names match exactly
3. Restart application to reload configuration
4. Check for syntax errors in JSON arrays

**Debug:**
```python
from app.config import settings
print(settings.FIREBASE_ALLOWED_DOMAINS)
```

### Problem: User Creation Fails

**Symptom:** Valid users cannot be created

**Check:**
1. Is domain in allowed list?
   ```bash
   echo $FIREBASE_ALLOWED_DOMAINS | grep "domain.com"
   ```
2. Does user have custom claims?
3. Is role in allowed list?
4. Check audit logs for rejection reason

---

## 📞 Support

For configuration help:

1. **Check Documentation:** Review this guide
2. **Run Tests:** `pytest tests/test_firebase_security.py`
3. **Check Logs:** Review application logs and audit logs
4. **Validate Config:** Run configuration test script

---

**Last Updated:** 2025-09-30
**Version:** 2.0.0
