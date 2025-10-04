# Backend Railway Deployment - Quick Start

## ⚡ 5-Minute Deploy

### 1. Railway Setup (1 min)
```bash
# In Railway Dashboard:
1. New Project → Deploy from GitHub
2. Select: clinica-oncologica-v02
3. Root Directory: backend-hormonia
4. Auto-detect: Dockerfile ✓
```

### 2. Critical Environment Variables (3 min)

**Copy-paste these into Railway Variables section:**

```bash
# === CRITICAL SECURITY (Generate new values!) ===
SECRET_KEY=GENERATE_NEW_64_CHAR_RANDOM_STRING
JWT_SECRET_KEY=GENERATE_NEW_64_CHAR_RANDOM_STRING
ENCRYPTION_KEY=GENERATE_NEW_32_CHAR_BASE64_STRING
MONTHLY_QUIZ_TOKEN_SECRET=GENERATE_NEW_64_CHAR_RANDOM_STRING

# === ENVIRONMENT ===
ENVIRONMENT=production
DEBUG=False
APP_NAME=NeoplasiaLitoral-Backend

# === DATABASE (from Supabase) ===
DATABASE_URL=postgresql+psycopg://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres

# === REDIS (from Redis Cloud or Railway) ===
ENABLE_REDIS=true
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
REDIS_PASSWORD=YOUR_PASSWORD
REDIS_HOST=YOUR_HOST
REDIS_PORT=YOUR_PORT
REDIS_SSL=true

# === SUPABASE ===
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_KEY
SUPABASE_USE_SERVICE_ROLE=true
SUPABASE_BYPASS_RLS=true

# === FIREBASE ===
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYOUR_KEY\n-----END PRIVATE KEY-----"
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk@project.iam.gserviceaccount.com
FIREBASE_ALLOWED_DOMAINS=["yourdomain.com"]
FIREBASE_BLOCK_PUBLIC_DOMAINS=true

# === AI (Gemini) ===
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025

# === CORS (Update with your URLs) ===
ALLOWED_ORIGINS=["https://your-frontend.railway.app"]
FRONTEND_URL=https://your-frontend.railway.app
FRONTEND_API_URL=https://your-backend.railway.app

# === SECURITY ===
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
```

### 3. Deploy (1 min)
```bash
# Railway will automatically:
✓ Build Docker image
✓ Run health checks
✓ Deploy to production
```

---

## 🔍 Verification Checklist

### After Deployment (30 seconds)

```bash
# 1. Check health
curl https://your-backend.railway.app/health

# Expected:
{
  "status": "healthy",
  "service": "hormonia-backend",
  "message": "Service is operational"
}

# 2. Check API docs (if DEBUG=True)
https://your-backend.railway.app/docs

# 3. Check Railway logs
# Dashboard → Deployments → View Logs
```

---

## 🚨 Common Issues

### 404 Application not found
```bash
✓ Root directory = backend-hormonia
✓ Dockerfile exists in backend-hormonia/
✓ Railway detected Dockerfile builder
```

### Health check fails
```bash
✓ DATABASE_URL correct format
✓ REDIS_URL with SSL (rediss://)
✓ All SUPABASE_ variables set
✓ Check Railway logs for errors
```

### Database connection error
```bash
✓ Format: postgresql+psycopg://...
✓ Use Supabase connection pooler
✓ Check Supabase allows Railway IPs
```

### Redis connection error
```bash
✓ REDIS_SSL=true
✓ REDIS_URL uses rediss:// (double s)
✓ Redis Cloud allows external connections
```

---

## 🔐 Generate Secure Keys

```python
# Run this to generate keys:
import secrets
from cryptography.fernet import Fernet

print("SECRET_KEY:", secrets.token_urlsafe(64))
print("JWT_SECRET_KEY:", secrets.token_urlsafe(64))
print("ENCRYPTION_KEY:", Fernet.generate_key().decode())
print("MONTHLY_QUIZ_TOKEN_SECRET:", secrets.token_urlsafe(64))
```

Or use online generator:
```bash
# Linux/Mac
openssl rand -base64 64

# Node.js
node -e "console.log(require('crypto').randomBytes(64).toString('base64'))"
```

---

## 📋 Minimum Required Variables

**20 Critical Variables** (service won't start without these):

1. SECRET_KEY
2. JWT_SECRET_KEY
3. ENCRYPTION_KEY
4. DATABASE_URL
5. REDIS_URL
6. REDIS_PASSWORD
7. REDIS_HOST
8. REDIS_PORT
9. SUPABASE_URL
10. SUPABASE_ANON_KEY
11. SUPABASE_SERVICE_ROLE_KEY
12. FIREBASE_ADMIN_PROJECT_ID
13. FIREBASE_ADMIN_PRIVATE_KEY
14. FIREBASE_ADMIN_CLIENT_EMAIL
15. GEMINI_API_KEY
16. ENVIRONMENT
17. ALLOWED_ORIGINS
18. FRONTEND_URL
19. MONTHLY_QUIZ_TOKEN_SECRET
20. REDIS_SSL

---

## 🎯 Next Steps

After successful deployment:

1. **Update Frontend**: Point frontend to backend URL
2. **Configure DNS**: Set up custom domain (optional)
3. **Enable Monitoring**: Configure Sentry (optional)
4. **Test Endpoints**: Verify all API routes work
5. **Setup Celery Worker**: Deploy worker service (optional)

---

## 📚 Full Documentation

- [Complete Deployment Guide](./BACKEND_RAILWAY_DEPLOYMENT.md)
- [All Environment Variables](./RAILWAY_ENV_VARS_COMPLETE.md)
- [DNS Configuration](./RAILWAY_DNS_INDEX.md)

---

## 💡 Pro Tips

1. **Use Railway CLI for faster variable setup**:
   ```bash
   railway variables set SECRET_KEY="your-key"
   ```

2. **Copy from .env file**:
   - Use `backend-hormonia/.env` as reference
   - Never commit real values to git
   - Generate new keys for production

3. **Monitor health endpoint**:
   - Set up external monitoring (UptimeRobot, etc.)
   - Check `/health/detailed` for component status

4. **Scale as needed**:
   - Start with 1 replica
   - Increase workers in Dockerfile if needed
   - Add more replicas for high traffic

---

## ⏱️ Expected Timeline

- **Setup**: 1 minute
- **Variables**: 3 minutes
- **Deploy**: 1 minute
- **Verification**: 30 seconds

**Total**: ~5-6 minutes

---

## 🆘 Need Help?

1. Check Railway logs first
2. Verify all environment variables
3. Test health endpoint
4. Review [Complete Guide](./BACKEND_RAILWAY_DEPLOYMENT.md)
5. Check [DNS Guide](./RAILWAY_DNS_INDEX.md) if frontend can't connect
