# E2E Testing Guide - Playwright

Complete guide for running, debugging, and maintaining End-to-End tests using Playwright.

## 📋 Table of Contents

- [Overview](#overview)
- [Setup](#setup)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Debugging](#debugging)
- [CI/CD Integration](#cicd-integration)
- [Coverage](#coverage)
- [Best Practices](#best-practices)

## 🎯 Overview

### What are E2E Tests?

End-to-End (E2E) tests validate complete user journeys through the application, including:
- User interface interactions
- API integrations
- Database operations
- External service mocking
- State consistency

### Test Coverage Goals

- **Current Coverage:** 45%
- **Target Coverage:** 70%
- **Critical Journeys:** 4 main user flows

### Technology Stack

- **Framework:** Playwright (Python async API)
- **Test Runner:** pytest
- **Browsers:** Chromium, Firefox, WebKit
- **Parallelization:** pytest-xdist
- **Mocking:** unittest.mock, custom fixtures

## 🚀 Setup

### 1. Install Dependencies

```bash
cd backend-hormonia

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium firefox
```

### 2. Environment Configuration

Create `.env.e2e` file:

```bash
# E2E Test Configuration
E2E_BASE_URL=http://localhost:8000
E2E_BROWSER=chromium
E2E_HEADLESS=true
E2E_SCREENSHOT=only-on-failure
E2E_VIDEO=retain-on-failure

# Database
E2E_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hormonia_test_e2e

# Mock Services
E2E_MOCK_WHATSAPP=true
E2E_MOCK_GEMINI=true
E2E_MOCK_FIREBASE=true

# Credentials
E2E_DOCTOR_EMAIL=doctor@test.com
E2E_DOCTOR_PASSWORD=Test@1234
```

### 3. Database Setup

```bash
# Create E2E test database
createdb hormonia_test_e2e

# Run migrations
alembic upgrade head
```

### 4. Start Application Server

```bash
# Terminal 1: Start backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Run E2E tests (after server starts)
pytest tests/e2e/
```

## 🧪 Running Tests

### Run All E2E Tests

```bash
pytest tests/e2e/ -v
```

### Run Specific Journey

```bash
# Patient Onboarding
pytest tests/e2e/test_patient_journey.py -v

# Webhook → AI Flow
pytest tests/e2e/test_webhook_ai_flow.py -v

# Doctor Dashboard
pytest tests/e2e/test_doctor_dashboard_journey.py -v

# Saga Resilience
pytest tests/e2e/test_saga_resilience_journey.py -v
```

### Run with Different Browser

```bash
# Chromium (default)
pytest tests/e2e/ --browser=chromium

# Firefox
pytest tests/e2e/ --browser=firefox

# WebKit (Safari)
pytest tests/e2e/ --browser=webkit
```

### Run in Headed Mode (See Browser)

```bash
pytest tests/e2e/ --headed
```

### Run with Screenshots and Videos

```bash
pytest tests/e2e/ \
  --screenshot=on \
  --video=on
```

### Parallel Execution

```bash
# Run with 4 workers
pytest tests/e2e/ -n 4
```

### With Coverage

```bash
pytest tests/e2e/ \
  --cov=app \
  --cov-report=html \
  --cov-report=term
```

## ✍️ Writing Tests

### Test Structure

```python
import pytest
from playwright.async_api import Page, expect

class TestMyJourney:
    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_complete_journey(
        self,
        page: Page,
        mock_whatsapp,
        mock_gemini,
    ):
        """Test description."""
        # Step 1: Setup
        # ...

        # Step 2: Execute action
        await page.goto('/dashboard')

        # Step 3: Verify result
        await expect(page.locator('.title')).to_contain_text('Dashboard')
```

### Available Fixtures

#### Browser Fixtures

```python
# Browser instance (session-scoped)
browser: Browser

# Browser context (function-scoped, isolated)
context: BrowserContext

# Page (function-scoped)
page: Page

# Authenticated page (with doctor login)
authenticated_page: Page
```

#### Mock Service Fixtures

```python
# Mock WhatsApp API
mock_whatsapp: Mock
mock_whatsapp.send_message(phone, message)
mock_whatsapp.messages_sent  # Count

# Mock Gemini AI
mock_gemini: Mock
mock_gemini.setup_response("AI response")
mock_gemini.call_count

# Mock Firebase
mock_firebase: Mock
await mock_firebase.create_user(email)
mock_firebase.users_created

# Chaos Engineering
chaos_monkey: Mock
chaos_monkey.fail_next('firebase_create_user', times=2)
```

#### Helper Fixtures

```python
# Generate webhook signature
generate_signature(payload: str) -> str

# Wait for saga completion
wait_for_saga = await wait_for_saga(saga_id, expected_status='COMPLETED')

# Get quiz questions
questions = await get_quiz_questions(session_id)
```

### Common Patterns

#### Navigate and Wait

```python
await page.goto('/patients')
await page.wait_for_load_state('networkidle')
```

#### Fill Form and Submit

```python
await page.fill('[name=email]', 'test@example.com')
await page.fill('[name=password]', 'Password123!')
await page.click('button[type=submit]')
```

#### API Request

```python
response = await page.request.post(
    '/api/v2/patients',
    headers={'Content-Type': 'application/json'},
    data=json.dumps(patient_data)
)
assert response.status == 201
```

#### Assertions

```python
# Element visible
await expect(page.locator('.success-message')).to_be_visible()

# Text content
await expect(page.locator('h1')).to_contain_text('Dashboard')

# Element count
count = await page.locator('.patient-row').count()
assert count > 0
```

## 🐛 Debugging

### Enable Debug Mode

```bash
# Run with headed browser and slowmo
pytest tests/e2e/test_patient_journey.py \
  --headed \
  --slowmo=1000  # 1 second delay between actions
```

### Playwright Inspector

```bash
# Interactive debugging
PWDEBUG=1 pytest tests/e2e/test_patient_journey.py
```

### Screenshots on Failure

Screenshots are automatically captured on test failure and saved to:
```
test-results/screenshots/failure-<timestamp>.png
```

### Videos on Failure

Videos are automatically recorded for failing tests:
```
test-results/videos/<test-name>.webm
```

### Traces

Traces include:
- Screenshots
- Console logs
- Network requests
- DOM snapshots

View traces:
```bash
playwright show-trace test-results/traces/trace-<timestamp>.zip
```

### Console Logs

Console messages are automatically logged during tests:
```python
page.on("console", lambda msg: print(f"Console: {msg.text}"))
```

### Network Traffic

Monitor network requests:
```python
context.on("request", lambda request: print(f"→ {request.method} {request.url}"))
context.on("response", lambda response: print(f"← {response.status} {response.url}"))
```

## 🔄 CI/CD Integration

### GitHub Actions Workflow

Located at: `.github/workflows/e2e-tests.yml`

**Features:**
- Runs on push and PR
- Matrix testing (Chromium + Firefox)
- Parallel execution
- Artifact upload (screenshots, videos, traces)
- Coverage reporting

**Trigger Manually:**

```bash
# Via GitHub UI: Actions → E2E Tests → Run workflow

# Via GitHub CLI
gh workflow run e2e-tests.yml
```

**View Results:**

```bash
gh run list --workflow=e2e-tests.yml
gh run view <run-id> --log
```

### Artifacts

After CI runs, download artifacts:

```bash
gh run download <run-id>
```

Artifacts include:
- Test reports (HTML)
- Screenshots (on failure)
- Videos (on failure)
- Traces (on failure)
- Coverage reports

## 📊 Coverage

### Generate Coverage Report

```bash
python scripts/e2e_coverage_report.py
```

**Output:**
- `test-results/e2e-coverage-report.html` - Interactive HTML report
- `test-results/coverage-summary.md` - Markdown summary

### Coverage Metrics

```bash
# View coverage in terminal
pytest tests/e2e/ --cov=app --cov-report=term

# Generate HTML report
pytest tests/e2e/ --cov=app --cov-report=html:htmlcov

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage Goals

| Category | Current | Target |
|----------|---------|--------|
| **E2E Coverage** | 45% | 70% |
| **User Journeys** | 2/4 | 4/4 |
| **Critical Endpoints** | 60% | 90% |

## 💡 Best Practices

### 1. Test Independence

✅ **DO:** Isolate each test
```python
@pytest.fixture(scope="function")
async def clean_db():
    # Create clean state
    yield
    # Cleanup after test
```

❌ **DON'T:** Depend on previous test state

### 2. Explicit Waits

✅ **DO:** Wait for specific conditions
```python
await page.wait_for_url('**/dashboard')
await expect(element).to_be_visible()
```

❌ **DON'T:** Use arbitrary sleep
```python
await asyncio.sleep(5)  # Flaky!
```

### 3. Descriptive Selectors

✅ **DO:** Use data attributes
```html
<button data-testid="submit-button">Submit</button>
```
```python
await page.click('[data-testid="submit-button"]')
```

❌ **DON'T:** Use brittle selectors
```python
await page.click('.btn.btn-primary.mt-3')  # Fragile!
```

### 4. Mock External Services

✅ **DO:** Mock WhatsApp, AI, Firebase
```python
mock_gemini.setup_response("Mocked AI response")
```

❌ **DON'T:** Call real external APIs

### 5. Comprehensive Assertions

✅ **DO:** Verify multiple aspects
```python
assert response.status == 200
assert patient['status'] == 'active'
assert patient.get('firebase_uid') is not None
```

❌ **DON'T:** Trust single assertion

### 6. Error Handling

✅ **DO:** Test error scenarios
```python
async def test_saga_failure_recovery(chaos_monkey):
    chaos_monkey.fail_next('firebase_create_user', times=2)
    # Test retry and recovery
```

### 7. Clean Test Data

✅ **DO:** Use unique identifiers
```python
patient_data = {
    'cpf': f'{datetime.now().timestamp():.0f}',
    'email': f'test_{uuid.uuid4()}@example.com'
}
```

## 🎯 Test Journeys

### 1. Patient Onboarding Journey (400+ LOC)

**File:** `tests/e2e/test_patient_journey.py`

**Steps:**
1. Doctor login
2. Create patient via UI
3. Verify WhatsApp message sent
4. Simulate patient webhook response
5. Verify saga execution
6. Verify Firebase account creation
7. Verify quiz flow initialization
8. Simulate quiz completion
9. Verify dashboard updates

### 2. Webhook → AI → Response Flow (350+ LOC)

**File:** `tests/e2e/test_webhook_ai_flow.py`

**Steps:**
1. Receive webhook
2. Validate signature
3. Check idempotency
4. Process with Flow Engine
5. Generate AI response
6. Send WhatsApp message
7. Persist messages

### 3. Doctor Dashboard Interactions (300+ LOC)

**File:** `tests/e2e/test_doctor_dashboard_journey.py`

**Steps:**
1. Login
2. View patient list (pagination)
3. Search/filter patients
4. View patient details
5. Edit patient data
6. View quiz results
7. Download report

### 4. Saga Resilience & Recovery (400+ LOC)

**File:** `tests/e2e/test_saga_resilience_journey.py`

**Steps:**
1. Trigger saga with failures
2. Verify compensation logic
3. Verify retry with backoff
4. Verify successful recovery
5. Verify state consistency
6. Verify no duplicates

## 🆘 Troubleshooting

### Issue: Tests Timing Out

**Solution:**
```bash
# Increase timeout
pytest tests/e2e/ --timeout=180
```

### Issue: Flaky Tests

**Solution:**
```python
# Use explicit waits
await page.wait_for_selector('.element', state='visible')

# Retry on failure
@pytest.mark.flaky(reruns=3, reruns_delay=2)
```

### Issue: Browser Not Found

**Solution:**
```bash
playwright install chromium
playwright install-deps  # Linux dependencies
```

### Issue: Database Conflicts

**Solution:**
```bash
# Reset test database
dropdb hormonia_test_e2e
createdb hormonia_test_e2e
alembic upgrade head
```

## 📚 Resources

- [Playwright Python Docs](https://playwright.dev/python/)
- [pytest-playwright Plugin](https://github.com/microsoft/playwright-pytest)
- [E2E Testing Best Practices](https://martinfowler.com/articles/practical-test-pyramid.html)

## 🤝 Contributing

When adding new E2E tests:

1. Follow existing patterns in test files
2. Add comprehensive docstrings
3. Use descriptive variable names
4. Include both happy path and error scenarios
5. Update this documentation
6. Ensure tests pass in CI

---

**Last Updated:** 2025-01-16
**Coverage Target:** 70% (from 45%)
**Test Suite:** 4 journeys, 12+ test cases
