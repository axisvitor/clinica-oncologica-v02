# Environment Variables - Quick Fix Reference

**Generated:** 2025-12-10
**Priority:** CRITICAL - Fix before next deployment

---

## 🔴 CRITICAL FIXES (Do These First)

### 1. Frontend Port Mismatch

**File:** `frontend-hormonia/.env`

**Find and Replace:**
```bash
# Lines 20-29 - CHANGE FROM:
VITE_API_BASE_URL=http://localhost:8007
VITE_API_ENDPOINT_URL=http://localhost:8007/api/v2
VITE_WS_BASE_URL=ws://localhost:8007/ws
VITE_WS_ENDPOINT_URL=ws://localhost:8007/ws

# TO:
VITE_API_BASE_URL=http://localhost:8000
VITE_API_ENDPOINT_URL=http://localhost:8000/api/v2
VITE_WS_BASE_URL=ws://localhost:8000/ws
VITE_WS_ENDPOINT_URL=ws://localhost:8000/ws
```

---

### 2. Remove Duplicate Variables

**File:** `backend-hormonia/.env`

**Delete These Lines:**

```bash
# Line 195 - DELETE (keep only QUIZ_TOKEN_SECRET on line 193)
MONTHLY_QUIZ_TOKEN_SECRET=vfqzMK9OmQYX7uZnkihOIpj38eiiu9zcJOcEt7MZaZI

# Line 407 - DELETE (keep HASH_SALT on line 406, or use the one defined in COMPLIANCE section)
HASH_SALT=5af51c11708d8d56dd5a9f8e5ca0071a3a662746ef415c1cecf3c04ef1c63d81
```

---

### 3. Fix Railway Template Variable Names

**File:** `backend-hormonia/.env.railway.template`

**Critical Corrections:**

```bash
# Line 44 - CHANGE FROM:
ENCRYPTION_KEY_CURRENT=REPLACE_WITH_ENCRYPTION_KEY

# TO:
SECURITY_ENCRYPTION_KEY=REPLACE_WITH_ENCRYPTION_KEY

# Line 31 - CHANGE FROM:
AUTH_JWT_ALGORITHM=HS256

# TO:
SECURITY_ALGORITHM=HS256
# AND ADD:
AUTH_JWT_SECRET_KEY=REPLACE_WITH_JWT_SECRET_KEY_DIFFERENT_FROM_MAIN

# Line 96 - CHANGE FROM:
REDIS_MAX_CONNECTIONS=10

# TO:
REDIS_POOL_MAX_CONNECTIONS=25

# Lines 179-181 - CHANGE FROM:
AUTH_SESSION_COOKIE_SECURE=true
AUTH_SESSION_COOKIE_HTTPONLY=true
AUTH_SESSION_COOKIE_SAMESITE=Strict

# TO:
SESSION_ENABLE_COOKIE_SECURE=true
SESSION_ENABLE_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Strict
SESSION_COOKIE_NAME=session_id
SESSION_COOKIE_PATH=/
SESSION_COOKIE_MAX_AGE_SECONDS=28800
```

---

### 4. Standardize Instance Name

**Frontend:** `frontend-hormonia/.env`
```bash
# Line 45 - Keep as is:
VITE_WHATSAPP_INSTANCE_NAME=clinica_oncologica
```

**Backend:** `backend-hormonia/.env`
```bash
# Line 127 - CHANGE FROM:
WHATSAPP_EVOLUTION_INSTANCE_NAME=instancia-teste

# TO:
WHATSAPP_EVOLUTION_INSTANCE_NAME=clinica_oncologica
```

---

## 🟠 HIGH PRIORITY FIXES

### 5. Standardize Clinic Name

**Choose ONE name and apply everywhere:**

**Option A: Use "Clínica Hormonia"**
```bash
# Frontend .env - Keep
VITE_CLINIC_NAME=Clínica Hormonia

# Backend .env - CHANGE:
WHATSAPP_CLINIC_NAME=Clínica Hormonia  # was Neoplasias Litoral
APP_NAME=Hormonia-Backend              # was NeoplasiaLitoral-Backend
```

**Option B: Use "Neoplasias Litoral"**
```bash
# Frontend .env - CHANGE:
VITE_CLINIC_NAME=Neoplasias Litoral    # was Clínica Hormonia

# Backend .env - Keep
WHATSAPP_CLINIC_NAME=Neoplasias Litoral
APP_NAME=NeoplasiaLitoral-Backend
```

**Recommendation:** Use "Clínica Hormonia" (matches frontend branding)

---

### 6. Fix Pool Sizes

**File:** `backend-hormonia/.env`

```bash
# Lines 53-56 - CHANGE TO:
DATABASE_POOL_SIZE=30
DATABASE_POOL_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=3600

# Line 78 - CHANGE TO:
REDIS_POOL_MAX_CONNECTIONS=50
```

**File:** `backend-hormonia/.env.railway.template`

```bash
# Lines 70-73 - CHANGE TO:
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_POOL_TIMEOUT_SECONDS=30
DATABASE_POOL_RECYCLE_SECONDS=3600

# Line 96 - CHANGE TO:
REDIS_POOL_MAX_CONNECTIONS=25
```

---

### 7. Update AI Model

**File:** `backend-hormonia/.env`

```bash
# Line 146 - CHANGE FROM:
AI_GEMINI_MODEL=gemini-2.5-flash-preview-09-2025

# TO:
AI_GEMINI_MODEL=gemini-2.0-flash-exp
```

---

### 8. Fix Quiz Base URL

**File:** `backend-hormonia/.env.example`

```bash
# Line 207 - CHANGE FROM:
QUIZ_BASE_URL=http://localhost:3001

# TO:
QUIZ_BASE_URL=http://localhost:3001/quiz/monthly
```

---

## 🟡 MEDIUM PRIORITY - Add Missing Variables

### 9. Add Redis DB Isolation to Railway Template

**File:** `backend-hormonia/.env.railway.template`

**Add after line 98 (REDIS_ENABLE_DECODE_RESPONSES):**

```bash
# =============================================================================
# REDIS - DATABASE ISOLATION
# =============================================================================
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB_NUMBER=1
REDIS_BROKER_DB_NUMBER=0
REDIS_SESSION_DB_NUMBER=2
REDIS_RATE_LIMIT_DB_NUMBER=3
```

---

### 10. Add Missing Sections to Development .env

**File:** `backend-hormonia/.env`

**Add at the end (after line 408):**

```bash
# =============================================================================
# VIRUS SCANNING (ClamAV)
# =============================================================================
CLAMAV_ENABLE_SERVICE=false
CLAMAV_HOST=localhost
CLAMAV_PORT=3310
CLAMAV_TIMEOUT_SECONDS=30
CLAMAV_ENABLE_FAIL_OPEN=true
CLAMAV_QUARANTINE_DIR=quarantine

# =============================================================================
# FILE SECURITY (CVE FIXES)
# =============================================================================
FILE_ENABLE_MIME_VALIDATION=true
FILE_ENABLE_MIME_STRICT=false
FILE_ENABLE_MIME_VARIANCE=true
FILE_ENABLE_SECURITY_SCAN=true
FILE_ENABLE_MACROS=false
FILE_ENABLE_PDF_JAVASCRIPT=false

# =============================================================================
# UPLOAD QUOTA
# =============================================================================
QUOTA_DEFAULT_USER_GB=1
QUOTA_PREMIUM_USER_GB=10
QUOTA_CACHE_TTL_SECONDS=300

# =============================================================================
# NOTIFICATIONS - EMAIL (SMTP)
# =============================================================================
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@clinica-hormonia.com
SMTP_ENABLE_TLS=true

# =============================================================================
# NOTIFICATIONS - SLACK
# =============================================================================
SLACK_WEBHOOK_URL=
SLACK_DEFAULT_CHANNEL=#alerts

# =============================================================================
# NOTIFICATIONS - PAGERDUTY
# =============================================================================
PAGERDUTY_API_KEY=
PAGERDUTY_SERVICE_KEY=

# =============================================================================
# NOTIFICATIONS - RETRY
# =============================================================================
NOTIFICATION_RETRY_ATTEMPTS=3
NOTIFICATION_RETRY_DELAY_SECONDS=5
```

---

## 🔐 SECURITY: Rotate Exposed Secrets

**⚠️ CRITICAL:** The following secrets are exposed in `.env` and MUST be rotated:

### Generate New Secrets

```bash
# 1. Generate new main secret key
python -c "import secrets; print('SECURITY_SECRET_KEY=' + secrets.token_urlsafe(64))"

# 2. Generate new JWT secret key (DIFFERENT from main secret)
python -c "import secrets; print('AUTH_JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"

# 3. Generate new encryption key
python -c "from cryptography.fernet import Fernet; print('SECURITY_ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# 4. Generate new CSRF secret
python -c "import secrets; print('SECURITY_CSRF_SECRET_KEY=' + secrets.token_urlsafe(32))"

# 5. Generate new quiz token secret
python -c "import secrets; print('QUIZ_TOKEN_SECRET=' + secrets.token_urlsafe(64))"

# 6. Generate new hash salt
python -c "import secrets; print('HASH_SALT=' + secrets.token_hex(32))"

# 7. Generate new webhook secret
python -c "import secrets; print('WHATSAPP_EVOLUTION_WEBHOOK_SECRET=' + secrets.token_urlsafe(32))"
```

### Update External Services

1. **AWS RDS:** Change database password
2. **Redis Cloud:** Rotate password
3. **Google Cloud:** Rotate Gemini API key
4. **Firebase:** Generate new service account key
5. **Evolution API:** Rotate WhatsApp API key

---

## 📋 Verification Checklist

After applying fixes, verify:

- [ ] Frontend connects to backend on port 8000
- [ ] No duplicate variables in any `.env` file
- [ ] All Railway template variables match code expectations
- [ ] Clinic name consistent across all files
- [ ] WhatsApp instance name matches frontend/backend
- [ ] Database pool sizes updated
- [ ] Redis pool sizes updated
- [ ] All secrets rotated
- [ ] `.env` not in git history
- [ ] `.gitignore` includes `.env`

---

## 🚀 Testing After Fixes

```bash
# 1. Test frontend connection
cd frontend-hormonia
npm run dev
# Open http://localhost:5173 - verify API calls work

# 2. Test backend startup
cd backend-hormonia
python -m uvicorn app.main:app --reload --port 8000
# Verify no validation errors

# 3. Test Railway deployment (dry-run)
railway up --detach
railway logs
# Check for environment variable errors
```

---

## 📞 Support

If you encounter issues after applying these fixes:

1. Check the full audit report: `docs/ENV_VARIABLES_AUDIT_REPORT.md`
2. Verify variable names match your code imports
3. Review Railway deployment logs for validation errors

---

**Last Updated:** 2025-12-10
**Version:** 1.0
