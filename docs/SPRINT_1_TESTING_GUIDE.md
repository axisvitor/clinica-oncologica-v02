# Sprint 1 Testing Guide

## Overview

This guide covers testing requirements, execution, and CI/CD integration for Sprint 1 of the project. Our goal is to increase test coverage from 26% to 40% minimum while maintaining code quality.

## Coverage Requirements

### Current Status
- **Baseline Coverage**: 26%
- **Sprint 1 Target**: 40%
- **Sprint 3 Goal**: 70%+

### Coverage Thresholds

#### Frontend (Vitest)
```typescript
coverage: {
  thresholds: {
    global: {
      statements: 40,
      branches: 40,
      functions: 40,
      lines: 40
    }
  }
}
```

#### Backend (Pytest)
```ini
--cov-fail-under=40
```

### What's Covered
- **Unit Tests**: Individual functions and components
- **Integration Tests**: Database operations, API endpoints
- **Performance Tests**: Cache hit rates, query optimization
- **Lazy Loading**: Code splitting, bundle optimization

### What's Excluded
- Test files (`**/*.test.*`, `**/*.spec.*`)
- Mock files (`src/mocks/**`, `**/__mocks__/**`)
- Configuration files (`**/*.config.*`)
- Type definitions (`**/*.d.ts`)
- Test utilities (`**/test-utils.*`, `**/setup.*`)
- Migration files (`*/migrations/*`, `*/alembic/*`)

## Running Tests

### Frontend Tests

#### Run All Tests
```bash
cd frontend-hormonia
npm run test
```

#### Run with Coverage
```bash
npm run test:coverage
```

#### Run Specific Test Suite
```bash
# Unit tests only
npm run test -- tests/unit

# Integration tests only
npm run test -- tests/integration

# Specific file
npm run test -- tests/integration/lazy-loading.test.tsx
```

#### Watch Mode (Development)
```bash
npm run test:watch
```

#### UI Mode
```bash
npm run test:ui
```

### Backend Tests

#### Run All Tests
```bash
cd backend-hormonia
pytest
```

#### Run with Coverage
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

#### Run Specific Test Suite
```bash
# Integration tests only
pytest tests/integration/

# Specific file
pytest tests/integration/test_query_cache_integration.py

# Specific test
pytest tests/integration/test_query_cache_integration.py::TestQueryCacheIntegration::test_cached_query_reduces_database_calls
```

#### Run with Markers
```bash
# Integration tests only
pytest -m integration

# Performance tests only
pytest -m performance

# Exclude slow tests
pytest -m "not slow"
```

#### Parallel Execution
```bash
pytest -n auto  # Use all CPU cores
pytest -n 4     # Use 4 workers
```

## Coverage Reports

### Frontend Coverage

#### HTML Report
```bash
npm run test:coverage
# Open: frontend-hormonia/coverage/index.html
```

#### Console Report
```bash
npm run test -- --coverage --reporter=verbose
```

#### JSON Report
```bash
npm run test:coverage
# Output: frontend-hormonia/coverage/coverage-final.json
```

#### LCOV Report (for CI/CD)
```bash
npm run test:coverage
# Output: frontend-hormonia/coverage/lcov.info
```

### Backend Coverage

#### HTML Report
```bash
pytest --cov=app --cov-report=html
# Open: backend-hormonia/htmlcov/index.html
```

#### Console Report
```bash
pytest --cov=app --cov-report=term-missing
```

#### JSON Report
```bash
pytest --cov=app --cov-report=json
# Output: backend-hormonia/coverage.json
```

#### LCOV Report
```bash
pytest --cov=app --cov-report=lcov
# Output: backend-hormonia/coverage.lcov
```

## Test Organization

### Frontend Test Structure
```
frontend-hormonia/tests/
├── unit/                 # Unit tests
│   ├── components/       # Component tests
│   ├── hooks/           # Hook tests
│   ├── services/        # Service tests
│   └── contexts/        # Context tests
├── integration/         # Integration tests
│   ├── lazy-loading.test.tsx
│   └── auth/
├── e2e/                 # End-to-end tests
│   └── auth/
└── setup.ts            # Test setup
```

### Backend Test Structure
```
backend-hormonia/tests/
├── unit/                # Unit tests
│   ├── services/       # Service tests
│   ├── utils/          # Utility tests
│   └── auth/           # Auth tests
├── integration/        # Integration tests
│   ├── test_query_cache_integration.py
│   └── auth/
├── middleware/         # Middleware tests
└── conftest.py        # Test configuration
```

## Writing Tests

### Frontend Test Template

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('ComponentName', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Feature A', () => {
    it('should do something specific', async () => {
      // Arrange
      const user = userEvent.setup();
      render(<Component />);

      // Act
      await user.click(screen.getByRole('button'));

      // Assert
      await waitFor(() => {
        expect(screen.getByText('Expected')).toBeInTheDocument();
      });
    });
  });
});
```

### Backend Test Template

```python
import pytest
from datetime import datetime

class TestFeatureName:
    """Test suite for feature description."""

    @pytest.fixture
    def sample_data(self, db_session):
        """Create sample data for tests."""
        data = Model(field="value")
        db_session.add(data)
        db_session.commit()
        return data

    def test_specific_behavior(self, db_session, sample_data):
        """Test specific behavior description."""
        # Arrange
        service = Service()

        # Act
        result = service.do_something(sample_data.id)

        # Assert
        assert result is not None
        assert result.field == "expected"
```

## Test Quality Standards

### Unit Tests
- ✅ Fast (< 100ms per test)
- ✅ Isolated (no database, no network)
- ✅ Focused (one behavior per test)
- ✅ Deterministic (same result every time)
- ✅ Clear naming (describes what and why)

### Integration Tests
- ✅ Real dependencies (database, cache)
- ✅ Test interactions between components
- ✅ Verify data flow
- ✅ Test error scenarios
- ✅ Clean state between tests

### Performance Tests
- ✅ Measure execution time
- ✅ Verify performance improvements
- ✅ Test cache hit rates
- ✅ Monitor memory usage
- ✅ Benchmark critical paths

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Test Coverage

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Frontend Dependencies
        run: cd frontend-hormonia && npm ci

      - name: Install Backend Dependencies
        run: cd backend-hormonia && pip install -r requirements.txt

      - name: Run Frontend Tests
        run: cd frontend-hormonia && npm run test:coverage

      - name: Run Backend Tests
        run: cd backend-hormonia && pytest --cov=app --cov-report=lcov

      - name: Upload Coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./frontend-hormonia/coverage/lcov.info,./backend-hormonia/coverage.lcov
          fail_ci_if_error: true

      - name: Check Coverage Thresholds
        run: |
          cd frontend-hormonia && npm run test:coverage
          cd ../backend-hormonia && pytest --cov=app --cov-fail-under=40
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "Running tests before commit..."

# Frontend tests
cd frontend-hormonia
npm run test:coverage || {
  echo "Frontend tests failed!"
  exit 1
}

# Backend tests
cd ../backend-hormonia
pytest --cov=app --cov-fail-under=40 || {
  echo "Backend tests failed!"
  exit 1
}

echo "All tests passed!"
```

## Troubleshooting

### Common Issues

#### Frontend

**Issue**: Tests timeout
```bash
# Solution: Increase timeout
npm run test -- --test-timeout=10000
```

**Issue**: Mock not working
```typescript
// Solution: Clear mocks between tests
beforeEach(() => {
  vi.clearAllMocks();
});
```

**Issue**: Coverage too low
```bash
# Solution: Check what's not covered
npm run test:coverage
# Open coverage/index.html to see uncovered lines
```

#### Backend

**Issue**: Database fixtures not working
```python
# Solution: Ensure proper fixture scope
@pytest.fixture(scope="function")
def db_session():
    # Create session
    yield session
    # Rollback
```

**Issue**: Async tests failing
```python
# Solution: Use pytest-asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None
```

**Issue**: Tests slow
```bash
# Solution: Run in parallel
pytest -n auto
```

## Best Practices

### Do's ✅
- Write tests first (TDD)
- Keep tests simple and focused
- Use descriptive test names
- Mock external dependencies
- Clean up after tests
- Test edge cases
- Verify error handling
- Measure performance improvements

### Don'ts ❌
- Don't test implementation details
- Don't share state between tests
- Don't skip tests in CI
- Don't ignore failing tests
- Don't test third-party libraries
- Don't use real API keys in tests
- Don't commit commented-out tests

## Metrics and Monitoring

### Track These Metrics
- **Coverage Percentage**: Aim for 40%+ (Sprint 1), 70%+ (Sprint 3)
- **Test Execution Time**: < 5 minutes total
- **Test Failure Rate**: < 1%
- **Flaky Test Rate**: 0%
- **Code Coverage Trend**: Increasing over time

### Coverage Badges

Add badges to README.md:

```markdown
![Frontend Coverage](https://img.shields.io/codecov/c/github/yourorg/yourrepo/frontend)
![Backend Coverage](https://img.shields.io/codecov/c/github/yourorg/yourrepo/backend)
```

## Next Steps

### Sprint 1 Completion Checklist
- [x] Configure coverage thresholds (40% minimum)
- [x] Create integration tests for query caching
- [x] Create integration tests for lazy loading
- [x] Update documentation
- [ ] Run full test suite and verify 40%+ coverage
- [ ] Set up CI/CD pipeline
- [ ] Add coverage badges to README
- [ ] Schedule Sprint 2 testing improvements

### Sprint 2 Goals
- Increase coverage to 55%
- Add E2E tests for critical flows
- Implement visual regression testing
- Add performance benchmarks

### Sprint 3 Goals
- Reach 70%+ coverage
- Full integration test suite
- Load testing
- Security testing

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Library](https://testing-library.com/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)

## Support

For questions or issues:
1. Check this guide first
2. Review test examples in codebase
3. Check CI/CD logs
4. Ask team in #testing channel
5. Create issue with `testing` label

---

**Last Updated**: 2025-10-09
**Version**: 1.0
**Sprint**: 1
