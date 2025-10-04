# Authentication Tests - Quick Start Guide

**⚡ Get testing in 2 minutes!**

## 🚀 Quick Start

### 1. Backend Tests (30 seconds)

```bash
cd backend-hormonia
pip install pytest pytest-asyncio pytest-cov
pytest tests/unit/services/test_firebase_auth_service.py -v
```

### 2. Frontend Unit Tests (30 seconds)

```bash
cd frontend-hormonia
npm install  # If not already installed
npm run test -- tests/unit/lib/test_firebase_client.ts
```

### 3. E2E Tests (1 minute)

```bash
cd frontend-hormonia
npx playwright install  # First time only
npx playwright test tests/e2e/auth/login.spec.ts
```

## 🎯 One-Command Test Runner

### Windows
```cmd
scripts\run-auth-tests.cmd --all --coverage
```

### Linux/Mac
```bash
chmod +x scripts/run-auth-tests.sh
./scripts/run-auth-tests.sh --all --coverage
```

### Options
- `--backend-only` - Run only backend tests
- `--frontend-only` - Run only frontend unit tests
- `--e2e-only` - Run only E2E tests
- `--coverage` - Generate coverage reports
- `--all` - Run all tests

## 📊 Expected Results

### Backend (12 tests)
```
tests/unit/services/test_firebase_auth_service.py::TestFirebaseAuthService::test_verify_valid_token PASSED
tests/unit/services/test_firebase_auth_service.py::TestFirebaseAuthService::test_verify_expired_token PASSED
tests/unit/services/test_firebase_auth_service.py::TestFirebaseAuthService::test_verify_invalid_token PASSED
... (9 more tests)

====== 12 passed in 0.45s ======
```

### Frontend Unit (7 tests)
```
✓ tests/unit/lib/test_firebase_client.ts (7)
  ✓ Firebase Client Authentication (7)
    ✓ should return user and session on successful login
    ✓ should return error on invalid credentials
    ✓ should return generic error for user-not-found
    ... (4 more tests)

Test Files  1 passed (1)
     Tests  7 passed (7)
```

### E2E (12 tests)
```
Running 12 tests using 2 workers

  ✓ tests/e2e/auth/login.spec.ts:15:5 › should display login form correctly (1.2s)
  ✓ tests/e2e/auth/login.spec.ts:24:5 › should show validation errors for empty fields (0.8s)
  ✓ tests/e2e/auth/login.spec.ts:42:5 › should login successfully with valid credentials (2.1s)
  ... (9 more tests)

  12 passed (15s)
```

## 🔧 Troubleshooting

### Backend Issues

**Issue**: `ModuleNotFoundError: No module named 'app'`
```bash
# Solution: Add backend to Python path
cd backend-hormonia
export PYTHONPATH=$PWD:$PYTHONPATH  # Linux/Mac
set PYTHONPATH=%CD%;%PYTHONPATH%    # Windows
pytest tests/unit/services/test_firebase_auth_service.py -v
```

**Issue**: `ImportError: cannot import name 'get_firebase_auth_service'`
```bash
# Solution: Check if firebase_auth_service.py exists
ls app/services/firebase_auth_service.py
# If missing, adjust import in test file
```

### Frontend Unit Issues

**Issue**: `Cannot find module 'firebase/auth'`
```bash
# Solution: Install Firebase
cd frontend-hormonia
npm install firebase
```

**Issue**: `TypeError: Cannot read properties of undefined`
```bash
# Solution: Check Firebase mocks in tests/setup.ts
# Ensure all Firebase methods are mocked
```

### E2E Issues

**Issue**: `Error: browserType.launch: Executable doesn't exist`
```bash
# Solution: Install Playwright browsers
npx playwright install
```

**Issue**: `TimeoutError: page.goto: Timeout 30000ms exceeded`
```bash
# Solution: Start dev server first
npm run dev  # In another terminal

# Or adjust playwright.config.ts to auto-start
```

**Issue**: `Error: Test failed: ECONNREFUSED`
```bash
# Solution: Check if dev server is running
curl http://localhost:5173  # Should return HTML
```

## 📋 Pre-Test Checklist

### Backend
- [ ] Python 3.11+ installed
- [ ] Virtual environment activated
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Firebase service exists: `app/services/firebase_auth_service.py`

### Frontend Unit
- [ ] Node.js 18+ installed
- [ ] Dependencies installed: `npm install`
- [ ] Firebase client exists: `src/lib/firebase-client.ts`
- [ ] Vitest configured: `vitest.config.ts`

### E2E
- [ ] Playwright installed: `npx playwright --version`
- [ ] Dev server running or auto-start configured
- [ ] Test credentials updated in `playwright.config.ts`
- [ ] Firebase config in `.env.local`

## 🎓 What Each Test Does

### Backend Tests
✅ Validates Firebase tokens are properly verified
✅ Ensures expired/invalid tokens are rejected
✅ Tests error handling for network issues
✅ Verifies custom claims (admin, roles) work

### Frontend Unit Tests
✅ Tests login flow with email/password
✅ Validates error messages are correct
✅ Ensures password reset works
✅ Tests logout functionality

### E2E Tests
✅ Full login journey from form to dashboard
✅ Auth state persists across page reloads
✅ Protected routes redirect to login
✅ Security: Rate limiting & user enumeration

## 📚 Next Steps

1. **Run the tests**: Use the quick start commands above
2. **Check coverage**: Use `--coverage` flag
3. **Fix failures**: Review test output for specific errors
4. **Expand tests**: See [AUTH_TEST_SUMMARY.md](./AUTH_TEST_SUMMARY.md) for next tests to add
5. **Read full guide**: See [TESTING.md](./TESTING.md) for comprehensive documentation

## 🆘 Need Help?

- **Backend Test Guide**: [TESTING.md - Backend Section](./TESTING.md#-backend-tests-python)
- **Frontend Test Guide**: [TESTING.md - Frontend Section](./TESTING.md#-frontend-tests-typescript)
- **Test Summary**: [AUTH_TEST_SUMMARY.md](./AUTH_TEST_SUMMARY.md)

---

**🎯 Goal**: Get 80%+ coverage on authentication flows

**📊 Current**: 31 tests covering token validation, login, logout, and security

**⏱️ Time**: ~2 minutes to run all tests
