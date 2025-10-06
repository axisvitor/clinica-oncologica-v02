# Railway Variables - Complete Configuration

## Critical Variables to Update (Copy-Paste Ready)

### 1. Database Connection (CRITICAL - Python 3.13 Compatible)

**⚠️ IMPORTANT**: Use `postgresql+psycopg://` for Python 3.13 compatibility (psycopg v3 driver)

```bash
DATABASE_URL=postgresql+psycopg://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

**Why `+psycopg`?**
- Railway uses Python 3.13 (from `runtime.txt`)
- SQLAlchemy with `postgresql://` tries to import `psycopg2` first (not installed)
- Using `postgresql+psycopg://` explicitly selects psycopg v3 driver
- Prevents `ModuleNotFoundError: No module named 'psycopg2'`

See [RAILWAY_PSYCOPG_FIX.md](RAILWAY_PSYCOPG_FIX.md) for detailed explanation.

### 2. Redis Configuration (Already Fixed - For Reference)

```bash
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_PASSWORD=6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
REDIS_HOST=redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=14149
REDIS_SSL=false
REDIS_SSL_CERT_REQS=none
REDIS_SSL_MIN_VERSION=
```

### 3. Celery Configuration (Matches Redis)

```bash
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
```

---

## Complete Variables Reference

### Core Application

```bash
ENVIRONMENT=production
DEBUG=false
APP_NAME=NeoplasiaLitoral-Backend
APP_VERSION=2.0.0
HOST=0.0.0.0
PORT=8080
```

### Security & JWT

```bash
SECRET_KEY=TVj0AS9r2O7FaF7uUri4NtUMOEqyK8jf74nrWdgTwZWcNGsYZvhXJd9nMn4UzeAgzbusLuklRgegN8cvCuj8uQ
JWT_SECRET_KEY=mYEeH00AvOtRUzpnqSDRerjFT4N-e5a1ywO-G5RCpwrHGH2Wktpx69qrMmCce9Lj8Tagsi_yTRHmpZg6JvX4oQ
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
BCRYPT_ROUNDS=12
ENABLE_FIELD_ENCRYPTION=true
ENCRYPTION_KEY=OUo9cgiZ-vxhNKke_T2_inkzRorYHZONx3NPS47Tp90
```

### Firebase Authentication

```bash
FIREBASE_ADMIN_PROJECT_ID=sistema-oncologico-auth
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk-fbsvc@sistema-oncologico-auth.iam.gserviceaccount.com
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
FIREBASE_ALLOWED_ROLES=["admin","super_admin","doctor","medico"]
FIREBASE_WEB_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
FIREBASE_WEB_PROJECT_ID=sistema-oncologico-auth
FIREBASE_WEB_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
FIREBASE_WEB_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
```

**IMPORTANT - Firebase Private Key**:
```bash
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDuxa6dCkF76Nel
eGW2MxIlfoqmr55uQzzSt7bDUgGLpRkdETwloAH+uC0LLl+PmYwJIX/TJ5ARE908
4gZDNteBDwodr7a7kRLS5Rz3bwNRBGe6LNVTJYJz8ASVfLhSVDMQCGjPj85Gv9b8
+AaeNILsyU+WrQ7LX5ywZJwiG6bxmlNw8YPhaDvSuvls9pxVXXbgeHe/Ylvnb+f1
BduCuhvDhJmbgzKhCdtKd8w9LS2/dlwfvKchtUcNxLs3V7jjGcDgZrRlMR4nw1FM
AwZXYeWwtebf7bHzIaboqkWP2HlMjBRXnwX/B3M9sikdMWFoLLvkIQNCGLQP8HG8
3CUX5I9DAgMBAAECggEAA1MUTdJ1O/Tvf7nP7LwETipXYt/CHHXqNGLjdA/BvsCD
O4DgbgOu022cDvJL2VOBfCUPwxBjdKFqrKzW+nuaf40GjohCSpVIBlCzWQyeJrQh
f5mdNMWqbdPTNIOii17pwRjk4LL3Y8vLAgWwDebcRdC9v3LUaGeB5oDYHa914RpG
mWFygB55JuM1ve2TFY1tViSJFMBg0Qkhkb9TCkjCh4Bnxt51pTV4QC6RZwejJvbV
yQjhM301Cbqj4FItga84wdbOmsQ4HRL+ePUmRnP5yjNjHVsezR7CMj7wPfWLRjry
8uEhWOg8AoQUW5S+R9miFqUTlCgj2/9YGoU9hUuwZQKBgQD7X/KyEzpp9OAMqxm8
IEnOMdSEmtH/yE51897nm5xHEjO0M/WpUCcYB5sKINGKz7WtfgwpCA/OICj528fN
b8ImsEpBbOGNjcRNn0AbGvRjGakjFzjAtl341j91IaYSwuCcx43DFACjzTK3AceM
O5zkpeJV1T9YC5aS0NdpvHFOnwKBgQDzKl84m4wl7gaDg1ojFRdWUmBGYpORK1li
m8OO4ATGK8sjDE74XZ5SBH3E44ksqDdsmV3yANf2oauTo6XZ0I9ynRYDJqaRgEu7
KrF1qF5K2g0Y3LM3Br368NqdrhTgo7K2CGZ7/8OkcgQKQmGYaMN6lZbY2DzPJLJ+
30weqT5Q3QKBgCvx1Rq+c8rMLVLpooEZ3+01FuLrseSWXukN7hztPj/KddF99+dW
hM8VnUwC+r7amvcufu+5YhH121P60Q4gCH/8965CW5gEfZnYSjuy1aBxfvkMeTZv
azQyODvA2yiSevPNiwHcgFQibkhB/mGMllv+h/fbZMx+kh8udUod0G0fAoGBAMbG
W2KF3NHguphlFpjZE+OvoR3IVUL1QbNXC0xPGff5Mqwq0p86wEHhhAIf0jGcLPps
gJxkTiZBUGV3AAuG7sxNVwIqZT1JuB5/LuO0R6g+iThKqYGQ1Fo+6ya8eDqN9nfR
dB1nHUHfJihQzUDuWuVpRQ9r7IGUSQlnde0WgmdNAoGBAOimEvJZcNk0fCrhjsv1
ceorapoHK5bkJNyY8OftYEoZstJ/HtnC88fy8zo5+JVnI91hmZy3mcO0xsHukIM2
VhYPPiDaqNUHPzNNNsbUcwRJx0+3eGFsH2yst+wYpG72Ooc4jJ6hIaB1HQbx7+iJ
/sY4m/57iobwzdr/DtS8q7er
-----END PRIVATE KEY-----"
```

### Supabase & Database

```bash
SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkzMDQ0NzksImV4cCI6MjA2NDg4MDQ3OX0.qF_byaebH1q78a6SYhGfCuGSotF523o1ZqTrwOBkPYg
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJzenB5cHl0ZGNpZ2d5YmJwbnJwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0OTMwNDQ3OSwiZXhwIjoyMDY0ODgwNDc5fQ.Ypo5TwjibCyvPWGdKsgjWRF_a3ZFXAk7afcAb4NSqXc
SUPABASE_AVATARS_BUCKET=avatars
SUPABASE_USE_SERVICE_ROLE=true
SUPABASE_BYPASS_RLS=true
```

### Database Pool Configuration

```bash
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=20
DB_STATEMENT_TIMEOUT=30000
DB_POOL_RECYCLE=3600
RLS_POOL_SIZE=30
RLS_POOL_MAX_OVERFLOW=50
```

### Redis & Celery

```bash
ENABLE_REDIS=true
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

### AI Services (Gemini)

```bash
GEMINI_API_KEY=AIzaSyBg8v_IuE16HjtCBF2VBlDUpQE55IDzs18
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_OUTPUT_TOKENS=4096
```

### WhatsApp Integration (Evolution API)

```bash
ENABLE_EVOLUTION=true
EVOLUTION_API_KEY=8635EBA73252-46A9-A965-7E534F24E72C
EVOLUTION_WEBHOOK_SECRET=F4pOsFNxxZKoTSo9usXU7A5Bkve_0xWKOibkFzejllQ
EVOLUTION_INSTANCE_NAME=clinica_oncologica
EVOLUTION_API_URL=https://evolution.axisvanguard.site
EVOLUTION_WEBHOOK_URL=https://clinica-oncologica-v02-production.up.railway.app/webhooks/whatsapp/evolution/clinica_oncologica
```

### Monthly Quiz Configuration

```bash
MONTHLY_QUIZ_VIA_LINK=true
MONTHLY_QUIZ_BASE_URL=https://quiz-interface-production.up.railway.app/quiz/monthly
MONTHLY_QUIZ_TOKEN_SECRET=vfqzMK9OmQYX7uZnkihOIpj38eiiu9zcJOcEt7MZaZI
MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS=72
```

### CORS & Security

```bash
ALLOWED_HOSTS=["frontend-production-18bb.up.railway.app","clinica-oncologica-v02-production.up.railway.app","*.up.railway.app"]
FRONTEND_API_URL=https://frontend-production-18bb.up.railway.app
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-interface-production.up.railway.app
SECURE_SSL_REDIRECT=true
SECURE_CONTENT_TYPE_NOSNIFF=true
SECURE_BROWSER_XSS_FILTER=true
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
```

### Monitoring & Logging

```bash
MONITORING_ENABLED=true
LOG_LEVEL=INFO
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
```

### LGPD Compliance

```bash
LGPD_COMPLIANCE_MODE=true
AUDIT_LOG_RETENTION_DAYS=365
DATA_RETENTION_DAYS=730
```

### File Upload

```bash
UPLOAD_DIR=uploads
MAX_UPLOAD_SIZE=10485760
AUTO_PROVISION_SUPABASE_USERS=true
```

---

## Step-by-Step Update Process

### 1. Update DATABASE_URL (Critical)

1. Go to Railway → Backend Service → Variables
2. Find `DATABASE_URL`
3. Replace with:
   ```
   postgresql://postgres.rszpypytdciggybbpnrp:NvbKfi1xMY7wzNof@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```
4. Save (Railway will auto-redeploy)

### 2. Verify Redis Variables (Should Already Be Correct)

Ensure these match:
- `REDIS_URL` starts with `redis://` (not `rediss://`)
- `REDIS_SSL=false`
- `REDIS_SSL_CERT_REQS=none`
- `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` use same `redis://` scheme

### 3. Wait for Deployment

Railway will automatically redeploy after saving variables.

### 4. Run Firebase Custom Claims Script

On your local machine:
```bash
cd backend-hormonia
python scripts/fix_firebase_custom_claims.py
```

### 5. Verify in Railway Logs

After deployment + Firebase script, check logs for:
- ✅ `Supabase client initialized successfully`
- ✅ `Firebase Admin SDK initialized successfully`
- ✅ `Redis client connected successfully`
- ❌ NO "Wrong password" errors
- ❌ NO "Invalid role in custom claims" errors

### 6. Test Endpoints

```bash
# Test authentication
curl -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  https://backend-production-90c3.up.railway.app/api/v1/auth/me

# Test WebSocket
wscat -c "wss://backend-production-90c3.up.railway.app/ws/connect?token=YOUR_FIREBASE_TOKEN"

# Test patients API
curl -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  https://backend-production-90c3.up.railway.app/api/v1/patients/
```

Expected: All return 200 OK (not 401 Unauthorized)

---

## Troubleshooting

### Database Still Shows "Wrong Password"
- Verify you copied the EXACT string with correct password
- Check Supabase dashboard for current connection string
- Try using direct connection instead of pooler

### Firebase Custom Claims Not Working
- User must log out and log back in after claims are set
- Verify script ran successfully
- Check Firebase Console → Authentication → Users → Custom Claims

### Redis Connection Failed
- Verify Redis Cloud console shows port 14149
- Confirm non-TLS endpoint (not TLS port)
- Check Redis password is current

---

**Last Updated**: 2025-10-06
**Status**: Ready for deployment
**Related**:
- [RAILWAY_LOGS_REVIEW.md](RAILWAY_LOGS_REVIEW.md)
- [REDIS_RAILWAY_FIX.md](REDIS_RAILWAY_FIX.md)
