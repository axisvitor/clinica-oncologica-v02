# CORS Test Suite - Quick Start Guide

## 🚀 Quick Setup (3 Steps)

### 1. Install Dependencies

```bash
# Install Python test dependencies
pip install pytest pytest-asyncio playwright fastapi httpx

# Install Playwright browsers
playwright install chromium
```

### 2. Start Backend

```bash
# Make sure your FastAPI backend is running
# Example:
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Run Tests

```bash
# Run all CORS tests
cd tests/e2e/cors
bash run_tests.sh

# Or use pytest directly
pytest tests/e2e/cors/ -v
```

## 🧪 Test Commands Cheat Sheet

```bash
# All CORS tests (E2E + Backend)
pytest tests/ -m cors -v

# Only E2E tests
pytest tests/e2e/cors/ -v

# Only backend unit tests
pytest tests/backend/cors/ -v

# Specific test file
pytest tests/e2e/cors/test_cors_preflight.py -v

# Single test function
pytest tests/e2e/cors/test_cors_preflight.py::TestCORSPreflight::test_preflight_from_allowed_origin_localhost_3000 -v

# Run with detailed output
pytest tests/e2e/cors/ -vv -s

# Run in parallel (faster)
pip install pytest-xdist
pytest tests/e2e/cors/ -n auto

# Generate HTML report
pip install pytest-html
pytest tests/e2e/cors/ --html=report.html --self-contained-html
```

## 🎯 Test Against Different Environments

```bash
# Local development
BACKEND_URL=http://localhost:8000 pytest tests/e2e/cors/ -v

# Staging environment
BACKEND_URL=https://staging.example.com pytest tests/e2e/cors/ -v

# Production (read-only tests only!)
BACKEND_URL=https://clinica-oncologica-production.up.railway.app pytest tests/e2e/cors/ -v
```

## ✅ Expected Results

All tests should **PASS** if CORS is configured correctly:

```
tests/e2e/cors/test_cors_preflight.py::TestCORSPreflight::test_preflight_from_allowed_origin_localhost_3000 PASSED
tests/e2e/cors/test_cors_preflight.py::TestCORSPreflight::test_preflight_from_allowed_origin_localhost_5173 PASSED
tests/e2e/cors/test_cors_preflight.py::TestCORSPreflight::test_preflight_from_production_origin PASSED
... [more tests] ...

========================== 50 passed in 15.42s ==========================
```

## 🐛 Common Issues

### ❌ "Backend not accessible"

**Problem**: Backend server is not running.

**Solution**:
```bash
# Start the backend
cd backend
uvicorn app.main:app --reload --port 8000
```

### ❌ "playwright._impl._errors.Error: Executable doesn't exist"

**Problem**: Playwright browsers not installed.

**Solution**:
```bash
playwright install chromium
```

### ❌ "ModuleNotFoundError: No module named 'pytest'"

**Problem**: Test dependencies not installed.

**Solution**:
```bash
pip install pytest pytest-asyncio playwright
```

### ❌ Tests fail with CORS errors

**Problem**: CORS middleware not configured correctly.

**Solution**: Check your FastAPI app has:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://clinica-oncologica-production.up.railway.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600
)
```

## 📊 Understanding Test Output

### ✅ Passing Test
```
test_cors_preflight.py::TestCORSPreflight::test_preflight_from_allowed_origin PASSED [100%]
```
- Test validated CORS headers correctly
- Origin is allowed
- Credentials are properly configured

### ❌ Failing Test
```
test_cors_preflight.py::TestCORSPreflight::test_preflight_from_allowed_origin FAILED [100%]
E   AssertionError: Access-Control-Allow-Origin header incorrect
```
- Check the assertion message
- Verify CORS middleware configuration
- Ensure backend is running correct version

## 🔍 Debugging Failed Tests

### View full error details
```bash
pytest tests/e2e/cors/test_cors_preflight.py -vv --tb=long
```

### Run with pdb debugger
```bash
pytest tests/e2e/cors/test_cors_preflight.py --pdb
```

### Manual CORS check with curl
```bash
# Preflight request
curl -X OPTIONS http://localhost:8000/api/patients \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  -v

# Actual request
curl http://localhost:8000/api/health \
  -H "Origin: http://localhost:3000" \
  -v
```

## 🎯 CI/CD Integration

### GitHub Actions Example

```yaml
name: CORS Tests

on: [push, pull_request]

jobs:
  cors-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio playwright fastapi httpx
          playwright install chromium

      - name: Start backend
        run: |
          cd backend
          uvicorn app.main:app --port 8000 &
          sleep 5

      - name: Run CORS tests
        run: |
          pytest tests/e2e/cors/ -v --tb=short
          pytest tests/backend/cors/ -v --tb=short
```

## 📝 Next Steps

After tests pass:
1. ✅ Commit the passing tests
2. ✅ Add to CI/CD pipeline
3. ✅ Run tests before each deployment
4. ✅ Monitor for CORS-related issues in production

## 🆘 Need Help?

- Check the full [README.md](README.md) for detailed documentation
- Review test code for specific validation logic
- Check backend CORS middleware configuration
- Verify environment variables are set correctly

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Playwright Python](https://playwright.dev/python/)
- [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [CORS Spec](https://fetch.spec.whatwg.org/#http-cors-protocol)
