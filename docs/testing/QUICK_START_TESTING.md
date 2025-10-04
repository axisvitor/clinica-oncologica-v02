# Quick Start: Firebase Authentication Testing

This guide helps you quickly validate the Firebase authentication system.

## Prerequisites

- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:5173`
- Firebase credentials configured in `.env` files

## 1. Quick Validation (5 minutes)

Run the automated validation script:

```bash
# From project root
chmod +x scripts/validate_firebase_auth.sh
./scripts/validate_firebase_auth.sh
```

This will check:
- ✅ Environment variables configured
- ✅ Backend running and healthy
- ✅ Auth endpoints responding correctly
- ✅ CORS configured
- ✅ Required files exist

## 2. Manual Login Test (2 minutes)

### Step 1: Start Services

```bash
# Terminal 1 - Backend
cd backend-hormonia
uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend-hormonia
npm run dev
```

### Step 2: Test Login

1. Open browser: `http://localhost:5173/medico/login`
2. Enter credentials:
   - Email: `medico@test.com`
   - Password: `Test123!@#`
3. Click "Entrar"
4. Should redirect to `/medico/dashboard`

### Step 3: Verify Token

Open DevTools (F12):

**Check Network:**
- Go to Network tab
- Click any API request to `/api/v1/`
- Check Headers → Request Headers
- Should see: `Authorization: Bearer eyJ...`

**Check Storage:**
- Go to Application tab
- Local Storage → `http://localhost:5173`
- Should see: `hormonia_access_token`

## 3. API Test with curl (1 minute)

### Get a Token

First, login through the UI and copy the token from DevTools:

```bash
# Application → Local Storage → hormonia_access_token
TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Test Protected Endpoint

```bash
# Test /auth/me endpoint
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Expected Output:
# {
#   "id": "uuid-here",
#   "email": "medico@test.com",
#   "full_name": "Dr. Test",
#   "role": "doctor",
#   "is_active": true,
#   ...
# }
```

### Test Invalid Token

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer invalid-token"

# Expected Output:
# {
#   "detail": "Invalid authentication token"
# }
# Status: 401
```

### Test Missing Token

```bash
curl -X GET "http://localhost:8000/api/v1/auth/me"

# Expected Output:
# {
#   "detail": "Not authenticated"
# }
# Status: 401
```

## 4. Common Issues & Solutions

### Issue: "Firebase authentication not configured"

**Solution:**
```bash
cd backend-hormonia

# Check if env vars are set
python3 -c "from app.config import settings; \
  print('Project ID:', settings.FIREBASE_ADMIN_PROJECT_ID); \
  print('Client Email:', settings.FIREBASE_ADMIN_CLIENT_EMAIL)"

# If empty, configure .env:
cp .env.example .env
# Edit .env and add Firebase credentials
```

### Issue: "CORS error in browser"

**Solution:**
```bash
# Check ALLOWED_ORIGINS in backend .env
grep ALLOWED_ORIGINS backend-hormonia/.env

# Should include:
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

### Issue: "Cannot connect to backend"

**Solution:**
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not running:
cd backend-hormonia
uvicorn app.main:app --reload
```

### Issue: "Login button does nothing"

**Solution:**
```bash
# Check browser console for errors
# Common causes:
# 1. Firebase config missing in frontend .env
# 2. Network request blocked by CORS
# 3. Backend not running

# Verify frontend .env:
cd frontend-hormonia
grep VITE_FIREBASE frontend-hormonia/.env
```

## 5. Run Unit Tests

### Backend Tests

```bash
cd backend-hormonia

# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run auth service tests
pytest tests/unit/services/test_firebase_auth_service.py -v

# Run all tests
pytest tests/ -v --cov=app
```

### Frontend Tests

```bash
cd frontend-hormonia

# Install test dependencies
npm install --save-dev vitest @testing-library/react

# Run auth context tests
npm run test -- tests/unit/contexts/MedicoAuthContext.test.tsx

# Run all tests
npm run test
```

## 6. Integration Tests

### Install Playwright

```bash
cd frontend-hormonia
npm install --save-dev @playwright/test

# Install browsers
npx playwright install
```

### Run E2E Tests

```bash
# Make sure backend and frontend are running

# Run login flow test
npx playwright test tests/e2e/auth/login_flow.spec.ts --headed

# Run all E2E tests
npx playwright test
```

## 7. Security Validation

### Test SQL Injection

```bash
# Test SQL injection prevention
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin'\'' OR '\''1'\''='\''1","password":"test"}'

# Expected: 410 Gone (login disabled)
```

### Test XSS

```bash
# Test XSS in error messages
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"<script>alert(\"XSS\")</script>","password":"test"}'

# Expected: Error message should be escaped
```

### Test CORS

```bash
# Test unauthorized origin
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Origin: https://malicious-site.com" \
  -H "Authorization: Bearer $TOKEN" \
  -v

# Expected: No Access-Control-Allow-Origin for malicious site
```

## 8. Performance Check

### Measure Token Validation Time

```bash
# Test token validation performance
time curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN" \
  -s -o /dev/null

# Expected: < 200ms
```

### Load Test

```bash
# Install hey (HTTP load testing tool)
# macOS: brew install hey
# Linux: go install github.com/rakyll/hey@latest

# Run load test (100 requests, 10 concurrent)
hey -n 100 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/auth/me

# Expected:
# - Success rate: 100%
# - Average response time: < 200ms
```

## 9. Testing Checklist

Use this checklist to verify authentication works:

- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] Can navigate to login page
- [ ] Login form validates email format
- [ ] Valid credentials login works
- [ ] Invalid password shows error
- [ ] Non-existent user shows error
- [ ] Token stored in localStorage
- [ ] Protected routes require auth
- [ ] API requests include Bearer token
- [ ] Logout clears token
- [ ] Page reload preserves auth
- [ ] Invalid token returns 401
- [ ] Missing token returns 401
- [ ] CORS allows frontend origin
- [ ] CORS blocks unknown origins

## 10. Next Steps

After validating the basics:

1. **Review Full Test Plan:** See `FIREBASE_AUTH_TESTING_PLAN.md`
2. **Implement Missing Tests:** Add test files to `tests/` directories
3. **Set up CI/CD:** Configure GitHub Actions to run tests
4. **Add Coverage Reports:** Track test coverage over time
5. **Performance Testing:** Add load tests for production readiness

## Resources

- **Full Testing Plan:** `docs/testing/FIREBASE_AUTH_TESTING_PLAN.md`
- **Firebase Docs:** https://firebase.google.com/docs/auth
- **Pytest Docs:** https://docs.pytest.org/
- **Playwright Docs:** https://playwright.dev/

## Support

If tests fail:

1. Check error messages in terminal output
2. Review browser DevTools console
3. Check backend logs: `backend-hormonia/logs/`
4. Verify environment variables are set
5. Ensure all dependencies are installed
6. Restart backend and frontend services

For detailed troubleshooting, see the main testing plan document.
