# 🔄 SECRET ROTATION CHECKLIST
## Step-by-Step Remediation Guide

**Incident Date:** 2025-10-06
**Status:** IN PROGRESS

---

## 🚀 QUICK START

### Priority Order
1. ⚠️ **Phase 1 (0-2h):** Rotate credentials that provide immediate system access
2. ⚠️ **Phase 2 (2-24h):** Rotate credentials requiring coordinated deployment
3. ✅ **Phase 3 (24-48h):** Verify and monitor
4. 🛡️ **Phase 4 (1 week):** Implement prevention measures

---

## ⏱️ PHASE 1: IMMEDIATE ROTATIONS (0-2 hours)

### ☐ Task 1: Rotate Firebase Admin Credentials
**Estimated Time:** 15 minutes

1. **Access Firebase Console:**
   - URL: https://console.firebase.google.com/project/sistema-oncologico-auth/settings/serviceaccounts
   - Navigate to: Service Accounts → Manage Service Account Permissions

2. **Delete Exposed Service Account:**
   ```
   Email: firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com
   ```

3. **Create New Service Account:**
   - Name: `firebase-adminsdk-neoplasialitoral-prod`
   - Role: Firebase Admin SDK Administrator Service Agent
   - Generate JSON key

4. **Update Railway Variables:**
   ```
   FIREBASE_ADMIN_PRIVATE_KEY=<paste from JSON: private_key>
   FIREBASE_ADMIN_CLIENT_EMAIL=<paste from JSON: client_email>
   ```

5. **Test:**
   ```bash
   # Check Railway logs for successful Firebase initialization
   # Look for: "Firebase Admin SDK initialized successfully"
   ```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 2: Rotate Supabase Service Role Key
**Estimated Time:** 10 minutes

1. **Access Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/rszpypytdciggybbpnrp/settings/api
   - Navigate to: Project Settings → API

2. **Reset Service Role Key:**
   - Click "Reset service_role key"
   - Confirm reset (⚠️ this will break existing connections)
   - Copy new key immediately

3. **Update Railway Variables:**
   ```
   SUPABASE_SERVICE_ROLE_KEY=<new_service_role_key>
   ```

4. **Test:**
   ```bash
   # Check backend can connect to Supabase
   curl https://clinica-oncologica-v02-production.up.railway.app/health
   ```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 3: Rotate Redis Password
**Estimated Time:** 20 minutes

1. **Access Redis Cloud Console:**
   - URL: https://app.redislabs.com/
   - Database: `redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149`

2. **Reset Password:**
   - Navigate to: Database → Configuration → Security
   - Click "Reset Password"
   - Copy new password

3. **Update Railway Variables:**
   ```
   REDIS_PASSWORD=<new_password>
   REDIS_URL=redis://default:<new_password>@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
   CELERY_BROKER_URL=redis://default:<new_password>@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
   CELERY_RESULT_BACKEND=redis://default:<new_password>@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
   ```

4. **Flush Redis Cache:**
   ```bash
   # Connect with new password and flush
   redis-cli -h redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com -p 14149 -a <new_password>
   > FLUSHALL
   > QUIT
   ```

5. **Restart Services:**
   - Restart `backend-web` service in Railway
   - Restart `backend-worker` service in Railway
   - Restart `backend-beat` service in Railway

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 4: Rotate Gemini API Key
**Estimated Time:** 10 minutes

1. **Access Google Cloud Console:**
   - URL: https://console.cloud.google.com/apis/credentials
   - Select project: sistema-oncologico-auth

2. **Delete Exposed Key:**
   - Find key: `AIzaSyBg8v_IuE16HjtCBF2VBlDUpQE55IDzs18`
   - Click "Delete"

3. **Create New API Key:**
   - Click "Create Credentials" → "API Key"
   - Restrict key to "Generative Language API"
   - Add HTTP referrer restrictions if possible

4. **Update Railway Variables:**
   ```
   GEMINI_API_KEY=<new_api_key>
   ```

5. **Review Billing:**
   - Check for unauthorized usage in past 48 hours
   - Document any anomalies

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 5: Rotate Evolution API Credentials
**Estimated Time:** 15 minutes

1. **Access Evolution API Dashboard:**
   - URL: https://evolution.axisvanguard.site
   - Instance: `clinica_oncologica`

2. **Regenerate API Key:**
   - Navigate to: Instance Settings → API Keys
   - Click "Regenerate API Key"
   - Copy new key

3. **Regenerate Webhook Secret:**
   - Navigate to: Instance Settings → Webhooks
   - Click "Regenerate Webhook Secret"
   - Copy new secret

4. **Update Railway Variables:**
   ```
   EVOLUTION_API_KEY=<new_api_key>
   EVOLUTION_WEBHOOK_SECRET=<new_webhook_secret>
   ```

5. **Re-register Webhook:**
   - URL: https://clinica-oncologica-v02-production.up.railway.app/webhooks/whatsapp/evolution/clinica_oncologica
   - Verify webhook is receiving events

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 6: Rotate Flow Nexus Session
**Estimated Time:** 5 minutes

1. **Logout from Flow Nexus:**
   ```bash
   npx flow-nexus@latest logout
   ```

2. **Login with New Session:**
   ```bash
   npx flow-nexus@latest login
   ```

3. **Remove from .env:**
   - Delete the `FLOW_NEXUS_SESSION` variable from root `.env`
   - This should be stored locally by Flow Nexus, not in `.env`

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 7: Rotate JWT Secret Keys (⚠️ REQUIRES USER RE-LOGIN)
**Estimated Time:** 20 minutes

1. **Generate New Secrets:**
   ```bash
   # SECRET_KEY
   python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

   # JWT_SECRET_KEY
   python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
   ```

2. **Prepare User Notification:**
   - Draft email/message: "System maintenance requires all users to re-login"
   - Schedule notification BEFORE deployment

3. **Update Railway Variables:**
   ```
   SECRET_KEY=<new_secret_key>
   JWT_SECRET_KEY=<new_jwt_secret_key>
   ```

4. **Deploy and Monitor:**
   - Deploy backend with new secrets
   - Monitor login attempts
   - Respond to user support requests

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________
**User Notification Sent:** [ ] Yes | [ ] No

---

## ⏱️ PHASE 2: HIGH PRIORITY ROTATIONS (2-24 hours)

### ☐ Task 8: Rotate Database Credentials
**Estimated Time:** 30 minutes (⚠️ Requires Coordinated Deployment)

1. **Access Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/rszpypytdciggybbpnrp/settings/database
   - Navigate to: Database Settings → Connection Pooling

2. **Reset Database Password:**
   - Click "Reset Database Password"
   - Copy new password immediately

3. **Update Connection String:**
   ```
   DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:<new_password>@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```

4. **Coordinated Deployment:**
   - Schedule maintenance window (off-peak hours)
   - Update Railway variable
   - Deploy immediately
   - Test database connectivity
   - Monitor error rates

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________
**Maintenance Window:** _______________

---

### ☐ Task 9: Rotate Encryption Key (⚠️ REQUIRES DATA MIGRATION)
**Estimated Time:** 1-2 hours

**⚠️ WARNING:** This requires re-encrypting all encrypted fields in the database.

1. **Backup Database:**
   ```bash
   # Create full database backup before proceeding
   pg_dump -h aws-0-sa-east-1.pooler.supabase.com -U postgres.rszpypytdciggybbpnrp -d postgres > backup_pre_encryption_rotation.sql
   ```

2. **Identify Encrypted Fields:**
   - Review models for fields using field-level encryption
   - Common fields: SSN, payment info, sensitive notes

3. **Generate New Key:**
   ```bash
   python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
   ```

4. **Create Migration Script:**
   ```python
   # Script to re-encrypt fields with new key
   # This should be run as a one-time migration
   ```

5. **Update Railway Variables:**
   ```
   ENCRYPTION_KEY=<new_encryption_key>
   ```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________
**Data Backup Created:** [ ] Yes | [ ] No

---

### ☐ Task 10: Rotate Monthly Quiz Token Secret
**Estimated Time:** 15 minutes

1. **Generate New Secret:**
   ```bash
   python -c "import secrets; print('MONTHLY_QUIZ_TOKEN_SECRET=' + secrets.token_urlsafe(32))"
   ```

2. **Update Railway Variables:**
   ```
   MONTHLY_QUIZ_TOKEN_SECRET=<new_secret>
   ```

3. **Invalidate Existing Tokens:**
   - All existing quiz access tokens will be invalidated
   - Users will need to request new quiz links

4. **Notify Support Team:**
   - Inform support team that quiz tokens have been reset
   - Prepare for increased support requests

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 11: Rotate Firebase Web API Key
**Estimated Time:** 15 minutes

1. **Access Firebase Console:**
   - URL: https://console.firebase.google.com/project/sistema-oncologico-auth/settings/general
   - Navigate to: Project Settings → General

2. **Regenerate Web API Key:**
   - Note: This may require recreating the web app configuration
   - Click "Add app" or regenerate existing web app

3. **Update Railway Variables:**
   ```
   # Backend
   FIREBASE_WEB_API_KEY=<new_api_key>

   # Frontend
   VITE_FIREBASE_API_KEY=<new_api_key>
   ```

4. **Deploy Both Services:**
   - Deploy backend-web
   - Deploy frontend

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

### ☐ Task 12: Rotate Supabase Anonymous Key
**Estimated Time:** 10 minutes

1. **Access Supabase Dashboard:**
   - URL: https://supabase.com/dashboard/project/rszpypytdciggybbpnrp/settings/api
   - Navigate to: Project Settings → API

2. **Reset Anonymous Key:**
   - Click "Reset anon key"
   - Copy new key

3. **Update Railway Variables:**
   ```
   # Backend
   SUPABASE_ANON_KEY=<new_anon_key>

   # Frontend
   VITE_SUPABASE_ANON_KEY=<new_anon_key>
   ```

4. **Deploy Both Services:**
   - Deploy backend-web
   - Deploy frontend

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Completed By:** _______________
**Timestamp:** _______________

---

## ✅ PHASE 3: VERIFICATION (24-48 hours)

### ☐ Task 13: Test All Integrations
**Estimated Time:** 1 hour

- [ ] Backend health check: `GET /health`
- [ ] Database connectivity: Test patient data retrieval
- [ ] Redis connectivity: Test caching
- [ ] Firebase authentication: Test login flow
- [ ] Supabase operations: Test file upload
- [ ] WhatsApp integration: Send test message
- [ ] AI features: Test Gemini API call
- [ ] Quiz tokens: Generate and validate token

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Test Results:** _______________

---

### ☐ Task 14: Monitor System Health
**Estimated Time:** Ongoing (48 hours)

Monitor the following metrics:
- [ ] Error rates (should be < 1%)
- [ ] Failed authentication attempts
- [ ] API response times
- [ ] Database query performance
- [ ] Redis connection pool

**Alert Thresholds:**
- Error rate > 5%: Immediate investigation
- Failed auth > 100/hour: Potential attack
- API latency > 2s: Performance issue

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Anomalies Detected:** _______________

---

### ☐ Task 15: Review Billing and Usage
**Estimated Time:** 30 minutes

Check for unauthorized usage:
- [ ] Gemini API usage (last 7 days)
- [ ] Firebase usage (authentication, storage)
- [ ] Supabase usage (database, storage)
- [ ] Redis Cloud usage
- [ ] Railway compute usage

**Cost Anomalies:** _______________

---

### ☐ Task 16: Scan Git History
**Estimated Time:** 30 minutes

1. **Check if .env files were committed:**
   ```bash
   git log --all --full-history -- "*/.env" "*/.env.local"
   ```

2. **If found, remove from history:**
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch **/.env **/.env.local" \
     --prune-empty --tag-name-filter cat -- --all

   git push origin --force --all
   ```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Secrets Found in Git:** [ ] Yes | [ ] No

---

### ☐ Task 17: Update Documentation
**Estimated Time:** 1 hour

- [ ] Update `.env.example` files with secure templates
- [ ] Document secret rotation procedures
- [ ] Update Railway deployment guides
- [ ] Create incident response runbook

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

---

## 🛡️ PHASE 4: PREVENTION MEASURES (1 week)

### ☐ Task 18: Implement Secret Scanning
**Estimated Time:** 2 hours

1. **Enable GitHub Advanced Security:**
   - Navigate to: Repository → Settings → Security → Secret scanning
   - Enable secret scanning
   - Enable push protection

2. **Install pre-commit hooks:**
   ```bash
   pip install pre-commit
   echo "
   repos:
     - repo: https://github.com/pre-commit/pre-commit-hooks
       rev: v4.4.0
       hooks:
         - id: detect-private-key
         - id: check-added-large-files

     - repo: https://github.com/Yelp/detect-secrets
       rev: v1.4.0
       hooks:
         - id: detect-secrets
   " > .pre-commit-config.yaml

   pre-commit install
   ```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

---

### ☐ Task 19: Security Training
**Estimated Time:** 4 hours

- [ ] Schedule security awareness training
- [ ] Review this incident with team
- [ ] Document lessons learned
- [ ] Update onboarding procedures

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed
**Training Date:** _______________

---

### ☐ Task 20: Quarterly Secret Rotation Policy
**Estimated Time:** 1 hour

Create policy document:
- Rotate all secrets every 90 days
- Use separate keys for dev/staging/prod
- Implement automated rotation where possible
- Document rotation procedures

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

---

## 📊 COMPLETION SUMMARY

### Phase Completion
- [ ] Phase 1: Immediate (0-2h)
- [ ] Phase 2: High Priority (2-24h)
- [ ] Phase 3: Verification (24-48h)
- [ ] Phase 4: Prevention (1 week)

### Total Time Invested: _______________
### Incident Closed Date: _______________
### Post-Incident Review Scheduled: _______________

---

## 🚨 ESCALATION CONTACTS

**Security Lead:** _______________
**DevOps Lead:** _______________
**Legal/Compliance:** _______________
**Data Protection Officer:** _______________

---

**Document Version:** 1.0
**Last Updated:** 2025-10-06
**Next Review:** After incident closure
