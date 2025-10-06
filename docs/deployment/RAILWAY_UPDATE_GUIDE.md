# 🚀 Railway Variables Update Guide

## Quick Start

```powershell
# Run automated script (updates ALLOWED_ORIGINS, Firebase flags, Supabase flags)
.\scripts\update-railway-vars.ps1

# Then manually update FIREBASE_ADMIN_PRIVATE_KEY via Railway UI (see below)
```

---

## What This Updates

### Backend Variables (Automated)
- ✅ `ALLOWED_ORIGINS` → `["https://frontend-production-18bb.up.railway.app","https://quiz-interface-production.up.railway.app"]`
- ✅ `FIREBASE_BLOCK_PUBLIC_DOMAINS` → `false`
- ✅ Removes deprecated `AUTO_PROVISION_SUPABASE_USERS`

### Frontend Variables (Automated)
- ✅ `VITE_SUPABASE_AUTH_ENABLED` → `false`
- ✅ `VITE_SUPABASE_REALTIME_ENABLED` → `false`
- ✅ `VITE_FIREBASE_ENABLED` → `true`

### Manual Update Required
- ⚠️ `FIREBASE_ADMIN_PRIVATE_KEY` (cannot be set via CLI due to newlines)

---

## Step-by-Step Instructions

### Step 1: Run Automated Script

```powershell
# From project root
.\scripts\update-railway-vars.ps1
```

**Expected Output:**
```
🚀 Railway Variables Update - Wave 2 Deployment
======================================================================

📦 Updating Backend Variables...
  - Setting ALLOWED_ORIGINS (with https://)...
  - Setting FIREBASE_BLOCK_PUBLIC_DOMAINS=false...
  - Removing deprecated AUTO_PROVISION_SUPABASE_USERS...

✅ Backend variables updated!
⚠️  FIREBASE_ADMIN_PRIVATE_KEY must be updated via Railway UI

📦 Updating Frontend Variables...
  - Setting VITE_SUPABASE_AUTH_ENABLED=false...
  - Setting VITE_SUPABASE_REALTIME_ENABLED=false...
  - Setting VITE_FIREBASE_ENABLED=true...

✅ Frontend variables updated!
```

---

### Step 2: Update FIREBASE_ADMIN_PRIVATE_KEY (Manual)

**Why Manual?** The Railway CLI doesn't properly handle multi-line private keys with `\n` escaping.

**Steps:**

1. **Open Railway Dashboard**: https://railway.app
2. **Select Your Project**: `clinica-oncologica-v02`
3. **Select Backend Service**: Click on the backend service
4. **Go to Variables Tab**: Click "Variables" in the left sidebar
5. **Edit FIREBASE_ADMIN_PRIVATE_KEY**:
   - Click on `FIREBASE_ADMIN_PRIVATE_KEY` variable
   - Delete existing value
   - Copy the **entire value** from `backend-hormonia\.env` (lines 39-67)
   - **CRITICAL**: Include the quotes `"-----BEGIN PRIVATE KEY-----` and `-----END PRIVATE KEY-----"`
   - Paste into Railway UI
6. **Save**: Click "Save" or "Update"
7. **Redeploy**: Railway will automatically trigger a redeploy

**Value to Copy** (from `backend-hormonia\.env`):

```
"-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDSCg/hxwTOQBra
+sS8/ZCXN4OKlKMmsxxjd4eMHZPE68bkYME8Q88n2b7tA39ws9cZgzQJQuAHuTNE
xvtP5a/7TKLIhwzMJs8MwxiBP7vbgYoapXlIfGzxSxnXXhD0CyJt2gi+pM3oSujj
yZg2hP+KUMnv9VdhUKWTbFFIIf/79o7BtB/u3w1jKO0wRNdzMYKSOP6gwMI4A0Ep
VUvZSwLJaK1XuIGZ6QLAHKL1CtqTLk7jDoxi/Wsal4ZTi8nrpeGhcZoOo8guSMlD
PSMLbX/shaSf/Wsayew3qU7J60E+4TlyGr0xzsa/Tf093YUmfzgb2AXWa6JmcKk0
BHomxMQPAgMBAAECggEAHjHnHZicVsA9fByP2vGC71JCPVJn8ADQxHXjDSAVZbpV
gfBs5yqCZeK2QWF+2SdpdVf4y5oLFeEofysx5scI2RIn1rcfflvX6ShE5hPRAFnr
jjAasvJ8QOYAhYcW3daZ8PvmxO1xUoMuXszU7oWJLQu3NCFrmehbnUl1l+6XW9PP
yb1zfiYIjCHuxDMmEy/l+npo2xJImTo4WVLq9HnnVSfVGxWrMzmzqeOJoxH8wpdx
SpYVUPZAJDiIPXuBiykCLwV1hrprzXPyPJ2FAW4JTfmhCIT3ES+IarcRjgkdgIpD
uljaHRMLeNIShxq1hjO1i4oGpmWX7cYD/QenGi3njQKBgQD69h2N796nvkEFvX+L
E/y6eR8USou7yKTqolS4qu9jgGTSK77lJ992NEvJuEonFWMzHoTYax5N5ygdkTGK
j6TXx4P0oyh4/Qhju/KbNknJwOjPNXXHtTT3a0pjC0mdLTJLWFIR0DTWSQAs+Pi3
KIQciTlxGhC4lYKz9ytRCr3aIwKBgQDWQZ3KrIi9g3itvsXVlLHc6kKKuCh0GbpF
o4oAtsBFqDiMhmVJHLTl4oeJwbAXEwCZektKs/6MlExbyMIm8OCgbGv0E9AgJc4w
HtXdYnkUTpyhMA5Ttgx4EpVWvqdp9S+0OLeGanf5IjSrip++aVSo2KO2Gt2uzWmK
zdxgeg4fJQKBgHorlfei7iF63OyOc6ig8kdU72xRXfTsmFwg6l172U33Ex29bhDg
eEhy7PImZPLh1ojsMn+opfgGr+C07gkmJHlnBzXwt6MuiwcCV/h3VTSCVNOKkuvF
qyNHd87/j7aUageD13AUi6RFpXA/Q9TmRGof43bL2ZgCML6rdMrfD81BAoGAOQnY
3wbVlFY2v1JlSnm+bAh1VIa4Rkg/HaDu8Ue1ohWpkEeLGU6qHfUTjinhHhNx+mnj
N2z5nCUyutCUV1eTBUI37w+DPbuyy366AqjfgPd4nTS067YwVZrk5OX2na+nVnwu
53ram5lumihaZI+X+SdLVgSK9ak7qrcpLwnvTn0CgYAMenpEeaqlPTyN8UmTzyxx
a84fwjN/GPDkR+djeDOEarXbxfqn1JdLvZSnLyByw9KGQNpQRm6B4TteWGBkf7wp
twGVWhzHEpd7soESO+ptdR8jq2uNXqP1yD0/DyFDk/nrO3AiB1A3zH47NxdMrmYg
0wDe+eK6h9cEpKLmWSGMLw==
-----END PRIVATE KEY-----
"
```

---

### Step 3: Verify Deployment

**Wait for Redeploy** (2-3 minutes):

```powershell
# Monitor backend logs
railway logs --service backend --tail

# Monitor frontend logs
railway logs --service frontend --tail
```

---

## Verification Checklist

### ✅ CORS Fixed
```powershell
railway logs --service backend | Select-String "ALLOWED_ORIGINS"
```

**Expected:**
```
✅ ALLOWED_ORIGINS loaded: ['https://frontend-production-18bb.up.railway.app', 'https://quiz-interface-production.up.railway.app']
```

**NOT Expected:**
```
❌ ALLOWED_ORIGINS is empty
❌ Allowed origins: ['https:frontend-production-18bb.up.railway.app']  # Missing //
```

---

### ✅ Firebase Auth Working
```powershell
railway logs --service backend | Select-String "Firebase"
```

**Expected:**
```
✅ Firebase Admin SDK initialized successfully
✅ Firebase auth configured with custom claims validation
```

**NOT Expected:**
```
❌ Failed to initialize Firebase Admin SDK
❌ Invalid private key format
```

---

### ✅ Frontend Using Firebase
```powershell
railway logs --service frontend | Select-String "VITE_FIREBASE"
```

**Expected:**
```
VITE_FIREBASE_ENABLED: true
VITE_SUPABASE_AUTH_ENABLED: false
```

---

### ✅ Login Performance
Test login twice and measure second request time:

```powershell
# Get your token first by logging in
$token = "YOUR_TOKEN_HERE"

# Measure second login performance
Measure-Command {
  curl -X GET "https://clinica-oncologica-v02-production.up.railway.app/api/v1/auth/me" `
    -H "Authorization: Bearer $token"
}
```

**Expected:**
- First login: 3-5s (normal - creates/links user)
- Second login: **<0.5s** ✅ (just timestamp updates)

---

### ✅ WebSocket Clean
```powershell
railway logs --service backend | Select-String "WebSocket"
```

**Expected:**
```
✅ WebSocket connection established
✅ Welcome message sent
```

**NOT Expected (duplicates):**
```
❌ WebSocket closed before welcome message (1000)
❌ WebSocket closed before welcome message (1000)
```

---

## Troubleshooting

### ❌ ALLOWED_ORIGINS Still Empty

**Problem:** CORS still not working after update

**Solution:**
```powershell
# Re-run the script
.\scripts\update-railway-vars.ps1

# Check current value
railway variables --service backend | Select-String "ALLOWED_ORIGINS"

# If still wrong, set manually via Railway UI
```

---

### ❌ Firebase Auth Failing

**Problem:** "Invalid private key format" or "Firebase initialization failed"

**Cause:** Private key not copied correctly (missing quotes or newlines)

**Solution:**
1. Re-copy **entire value** from `backend-hormonia\.env` lines 39-67
2. **Include the surrounding quotes**: `"-----BEGIN...-----"`
3. Paste into Railway UI (it handles newlines automatically)
4. Save and wait for redeploy

---

### ❌ Frontend Still Using Supabase

**Problem:** Login goes to Supabase instead of Firebase

**Solution:**
```powershell
# Re-run frontend variable updates
cd frontend-hormonia
railway variables --set VITE_FIREBASE_ENABLED=true
railway variables --set VITE_SUPABASE_AUTH_ENABLED=false

# Trigger redeploy
railway up --detach
```

---

## Post-Update Actions

After all variables are updated and verified:

1. **Monitor Logs** for 5-10 minutes to catch any errors
2. **Test Login Flow** with admin account
3. **Check Dashboard** loads correctly
4. **Verify WebSocket** connects without duplicates
5. **Measure Performance** (login should be <0.5s on repeat)

---

## Security Reminder

⚠️ **CRITICAL**: After confirming everything works, rotate credentials:

**Priority 1 (0-4h):**
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `FIREBASE_ADMIN_PRIVATE_KEY` (new service account)
- `SUPABASE_SERVICE_ROLE_KEY`
- `ENCRYPTION_KEY`

**Priority 2 (24h):**
- `DATABASE_URL` password
- `REDIS_PASSWORD`
- `GEMINI_API_KEY`
- `EVOLUTION_API_KEY`

See: [docs/security/ROTATION_CHECKLIST.md](../security/ROTATION_CHECKLIST.md)

---

**Last Updated:** 2025-10-06
**Status:** ✅ Ready to Execute
**Next Step:** Run `.\scripts\update-railway-vars.ps1`
