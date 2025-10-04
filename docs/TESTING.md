# Testing Guide - Clínica Oncológica Hormonia

## 📋 Overview

This document describes the testing strategy and execution for the Hormonia Clinic application.

## 🧪 Test Structure

```
backend-hormonia/
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── test_firebase_auth_service.py
│   └── integration/
└── pytest.ini

frontend-hormonia/
├── tests/
│   ├── setup.ts
│   ├── unit/
│   │   └── lib/
│   │       └── test_firebase_client.ts
│   └── e2e/
│       └── auth/
│           └── login.spec.ts
├── vitest.config.ts
└── playwright.config.ts
```

## 🎯 Test Coverage Goals

- **Statements**: >80%
- **Branches**: >75%
- **Functions**: >80%
- **Lines**: >80%

## 🔧 Backend Tests (Python)

### Setup

```bash
cd backend-hormonia
pip install pytest pytest-asyncio pytest-cov
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/services/test_firebase_auth_service.py -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Test Markers

- `@pytest.mark.unit` - Unit tests (fast, isolated)
- `@pytest.mark.integration` - Integration tests (requires external services)
- `@pytest.mark.security` - Security-focused tests
- `@pytest.mark.slow` - Slow tests (performance, load testing)

### Writing Backend Tests

```python
import pytest
from unittest.mock import patch

class TestYourService:
    @pytest.fixture
    def service(self):
        """Fixture for service instance"""
        return YourService()

    @patch('module.dependency')
    async def test_your_method(self, mock_dep, service):
        """Test description"""
        # Arrange
        mock_dep.return_value = expected_value

        # Act
        result = await service.your_method()

        # Assert
        assert result == expected_value
        mock_dep.assert_called_once()
```

## 🔧 Frontend Tests (TypeScript)

### Setup

```bash
cd frontend-hormonia
npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom
npm install -D playwright @playwright/test
```

### Running Tests

```bash
# Unit tests (Vitest)
npm run test                    # Run all unit tests
npm run test:ui                 # Run with UI
npm run test:coverage           # Run with coverage

# E2E tests (Playwright)
npx playwright test             # Run all E2E tests
npx playwright test --ui        # Run with UI
npx playwright test --headed    # Run with browser visible
npx playwright show-report      # View test report
```

### Writing Frontend Unit Tests

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

describe('YourComponent', () => {
  it('should render correctly', () => {
    // Arrange
    render(<YourComponent />)

    // Act
    const element = screen.getByText('Expected Text')

    // Assert
    expect(element).toBeInTheDocument()
  })
})
```

### Writing E2E Tests

```typescript
import { test, expect } from '@playwright/test'

test('should complete user flow', async ({ page }) => {
  // Navigate
  await page.goto('/login')

  // Interact
  await page.fill('[name="email"]', 'test@example.com')
  await page.fill('[name="password"]', 'password123')
  await page.click('button[type="submit"]')

  // Assert
  await expect(page).toHaveURL(/dashboard/)
})
```

## 🔒 Security Tests

### Backend Security Tests

```python
@pytest.mark.security
async def test_sql_injection_prevention(self):
    """Test SQL injection is prevented"""
    malicious_input = "'; DROP TABLE users; --"
    result = await service.query(malicious_input)
    assert result is not None
```

### Frontend Security Tests

```typescript
test('should sanitize XSS attempts', () => {
  const xssPayload = '<script>alert("XSS")</script>'
  const sanitized = sanitizeInput(xssPayload)
  expect(sanitized).not.toContain('<script>')
})
```

## 📊 Test Reports

### Backend Coverage Report

```bash
cd backend-hormonia
pytest --cov=app --cov-report=html
# Open htmlcov/index.html in browser
```

### Frontend Coverage Report

```bash
cd frontend-hormonia
npm run test:coverage
# Open coverage/index.html in browser
```

### Playwright Test Report

```bash
npx playwright show-report
```

## 🎯 CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run test:coverage
      - run: npx playwright install --with-deps
      - run: npx playwright test
```

## 🐛 Debugging Tests

### Backend Debugging

```bash
# Run with verbose output
pytest -vv

# Run with print statements
pytest -s

# Run specific test with debugging
pytest tests/unit/services/test_firebase_auth_service.py::TestFirebaseAuthService::test_verify_valid_token -vv
```

### Frontend Debugging

```bash
# Vitest debugging
npm run test -- --reporter=verbose

# Playwright debugging
npx playwright test --debug
npx playwright test --headed --slowmo=1000
```

## 📝 Best Practices

### 1. Test Naming
- Use descriptive names: `test_verify_valid_token_returns_user_data`
- Follow pattern: `test_<action>_<expected_result>`

### 2. Test Structure
- **Arrange**: Set up test data and mocks
- **Act**: Execute the code under test
- **Assert**: Verify expected results

### 3. Test Isolation
- Each test should be independent
- Use fixtures/setup for common state
- Clean up after tests

### 4. Test Coverage
- Aim for >80% coverage
- Focus on critical paths first
- Don't chase 100% - test what matters

### 5. Performance
- Keep unit tests fast (<100ms)
- Use mocks for external dependencies
- Run expensive tests separately

## 🔄 Continuous Testing

### Watch Mode

```bash
# Backend
pytest --watch

# Frontend
npm run test -- --watch
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## 📚 Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [Testing Library](https://testing-library.com/)

## 🆘 Troubleshooting

### Common Issues

**Issue**: Tests timeout
**Solution**: Increase timeout in config or use `@pytest.mark.timeout(seconds)`

**Issue**: Mock not working
**Solution**: Check import path and patch location

**Issue**: Playwright can't find element
**Solution**: Use `page.waitForSelector()` before interaction

**Issue**: Coverage not accurate
**Solution**: Check `.coveragerc` excludes and source paths
