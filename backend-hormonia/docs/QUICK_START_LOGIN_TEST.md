# 🚀 Quick Start - Login Test

**Goal:** Test login system with real credentials from .env file

---

## ⚡ Quick Start (3 commands)

```bash
# 1. Run the test to verify configuration
python3 backend-hormonia/scripts/login-tests/test_login_complete.py

# 2. Start backend server
./backend-hormonia/scripts/start_backend.sh

# 3. In another terminal, start frontend
cd frontend-hormonia && npm run dev
```

Then open http://localhost:5173 and login with:
- **Email:** `admin@neoplasiaslitoral.com`
- **Password:** `Admin@123456!`

---

## 📊 Test Results Summary

✅ **80% Complete** - System is configured and ready

| Component | Status |
|-----------|--------|
| Environment Config | ✅ Ready |
| Firebase User | ✅ Exists (admin role) |
| Database | ✅ Configured |
| Redis Cache | ✅ Configured |
| Backend Server | ⚠️ **Start Required** |

---

## 🔍 What to Check After Login

### 1. Backend Console
Look for these messages:
```
✅ Token verified for user: admin@neoplasiaslitoral.com
✅ DB Session created: session_id=...
✅ Redis Session created: session_id=...
✅ Cookie set: session_id=...
```

### 2. Browser DevTools (F12)
1. Go to **Application** tab
2. Click **Cookies** → `localhost:5173`
3. Find `session_id` cookie
4. Verify it has a UUID value

### 3. Test API (Optional)
```bash
# Copy session_id from browser cookies, then:
curl http://localhost:8000/api/v2/auth/verify-session \
     -H "Cookie: session_id=YOUR_SESSION_ID"
```

---

## 📁 Created Files

| File | Purpose |
|------|---------|
| `backend-hormonia/scripts/login-tests/test_login_complete.py` | ⭐ **Main test script** |
| `backend-hormonia/scripts/start_backend.sh` | Backend startup helper |
| `backend-hormonia/docs/repo/TEST_REPORT_LOGIN.md` | 📄 **Full documentation** |
| `backend-hormonia/docs/repo/LOGIN_TEST_SUMMARY.md` | Executive summary |

---

## 🆘 Troubleshooting

**Backend won't start?**
```bash
# Kill existing process on port 8000
lsof -ti:8000 | xargs kill -9

# Install dependencies
cd backend-hormonia
pip install -r requirements.txt
```

**Login fails?**
- Check if user exists: Test already verified user exists ✅
- Check Firebase credentials in `.env` ✅
- Check backend logs for errors

**No cookie set?**
- Check CORS configuration in `.env`
- Verify frontend URL matches `CORS_ALLOWED_ORIGINS`

---

## 📞 Need Help?

1. **Read full report:** `backend-hormonia/docs/repo/TEST_REPORT_LOGIN.md`
2. **Check backend logs:** `backend-hormonia/logs/`
3. **Review test output:** Run `python3 backend-hormonia/scripts/login-tests/test_login_complete.py`

---

## ✅ Success Criteria

You'll know the test is successful when:
- ✅ Backend shows "Token verified for user: admin@neoplasiaslitoral.com"
- ✅ Browser has `session_id` cookie
- ✅ You can access authenticated pages
- ✅ API returns user data with session

---

**Quick Test:** `python3 backend-hormonia/scripts/login-tests/test_login_complete.py`
**Quick Start:** `./backend-hormonia/scripts/start_backend.sh`
**Quick Login:** http://localhost:5173 (admin@neoplasiaslitoral.com / Admin@123456!)
