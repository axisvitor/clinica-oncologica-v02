# 🧪 Baseline Tests - Services Consolidation

## Overview

This directory contains **baseline tests** that validate the **current behavior** of services **before consolidation**. These tests serve as a safety net to ensure nothing breaks during the consolidation process.

## Purpose

### Why Baseline Tests?

1. **Safety Net**: Ensure consolidation doesn't break existing functionality
2. **Documentation**: Document current behavior and APIs
3. **Regression Detection**: Quickly identify any changes in behavior
4. **Confidence**: Provide confidence to refactor aggressively
5. **Comparison**: Baseline for performance comparisons after consolidation

### When to Run

- **Before**: Run before starting any consolidation
- **During**: Run after each consolidation step
- **After**: Run after consolidation is complete
- **Always**: Should be part of CI/CD pipeline

## Test Structure

```
tests/services/baseline/
├── README.md                      # This file
├── test_ai_baseline.py           # AI Services (5 files → 1)
├── test_cache_baseline.py        # Cache Services (10 files → 1)
├── test_alert_baseline.py        # Alert Services (3 files → 1)
├── test_flow_baseline.py         # Flow Services (17 files → 4) - TODO
├── test_message_baseline.py      # Message Services (8+ → 2) - TODO
└── test_quiz_baseline.py         # Quiz Services (12+ → 3) - TODO
```

## Current Status

### ✅ Phase 1 - Low Risk (Templates Created)

| Service Group | Files | Status | Tests | Coverage |
|---------------|-------|--------|-------|----------|
| AI Services | 5→1 | 📝 Template | 288 LOC | 0% (needs implementation) |
| Cache Services | 10→1 | 📝 Template | 405 LOC | 0% (needs implementation) |
| Alert Services | 3→1 | 📝 Template | 421 LOC | 0% (needs implementation) |

### 🔲 Phase 2 - Medium Risk (TODO)

| Service Group | Files | Status | Tests | Coverage |
|---------------|-------|--------|-------|----------|
| Flow Services | 17→4 | 📋 Planned | - | - |
| Message Services | 8→2 | 📋 Planned | - | - |
| Quiz Services | 12→3 | 📋 Planned | - | - |

### 🔲 Phase 3 - High Risk (TODO)

| Service Group | Files | Status | Tests | Coverage |
|---------------|-------|--------|-------|----------|
| Audit Services | 3→1 | 📋 Planned | - | - |
| Monitoring Services | 8→2 | 📋 Planned | - | - |
| Analytics Services | 5→2 | 📋 Planned | - | - |
| WebSocket Services | 5→1 | 📋 Planned | - | - |

## How to Use

### Step 1: Analyze Service Implementation

Before implementing tests, analyze the actual service:

```bash
# Read the service code
cat app/services/ai.py
cat app/services/ai_cache.py
cat app/services/ai_cache_service.py
cat app/services/ai_redis_cache.py
cat app/services/ai_batch_processor.py

# Find who uses it
grep -r "from app.services.ai import" app/
grep -r "AIService" app/
```

### Step 2: Implement Tests

Replace the `@pytest.mark.skip` decorators with actual test implementations:

```python
# Before (Template)
@pytest.mark.skip(reason="Template - implement after analyzing actual service")
def test_service_initialization(self):
    pass

# After (Implemented)
def test_service_initialization(self, mock_db, mock_cache):
    service = AIService(db=mock_db, cache=mock_cache)
    assert service is not None
    assert service.db == mock_db
    assert service.cache == mock_cache
```

### Step 3: Run Tests

```bash
# Run specific test file
pytest tests/services/baseline/test_ai_baseline.py -v

# Run all baseline tests
pytest tests/services/baseline/ -v

# Run with coverage
pytest tests/services/baseline/test_ai_baseline.py --cov=app.services.ai --cov-report=html

# Run performance tests only
pytest tests/services/baseline/test_ai_baseline.py -k "performance" -v
```

### Step 4: Document Results

After implementing and running tests, document:

1. **Coverage**: What percentage of code is covered?
2. **Performance**: What are the baseline metrics?
3. **Known Issues**: Any bugs or limitations discovered?
4. **Public API**: What methods/classes are actually used externally?

### Step 5: Use During Consolidation

During consolidation, run baseline tests frequently:

```bash
# Before making changes
pytest tests/services/baseline/test_ai_baseline.py -v

# After each change
pytest tests/services/baseline/test_ai_baseline.py -v

# If tests fail, you broke something - fix it or rollback
```

## Test Categories

Each baseline test file includes:

### 1. Unit Tests
- Test individual methods and classes
- Mock external dependencies
- Fast execution (< 100ms per test)

### 2. Integration Tests
- Test services working together
- Use real dependencies where possible
- Validate inter-service communication

### 3. Performance Tests
- Benchmark current performance
- Establish baselines for comparison
- Detect performance regressions

### 4. Edge Case Tests
- Empty inputs
- Very large inputs
- Invalid inputs
- Concurrent access
- Error scenarios

## Best Practices

### ✅ DO

- **Run tests before consolidation** - Establish baseline
- **Run tests after each change** - Catch regressions immediately
- **Document test failures** - Understand why tests fail
- **Keep tests updated** - As behavior changes, update tests
- **Measure performance** - Benchmark before and after
- **Test edge cases** - Don't just test happy paths

### ❌ DON'T

- **Skip tests** - They exist for a reason
- **Modify tests to pass** - Fix code, not tests
- **Remove failing tests** - Investigate why they fail
- **Test implementation details** - Test public APIs only
- **Over-mock** - Use real dependencies when practical
- **Ignore performance** - Slow tests indicate problems

## Troubleshooting

### Tests Won't Run

```bash
# Missing dependencies?
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov

# Can't find services?
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Tests Fail

```bash
# Run with verbose output
pytest tests/services/baseline/test_ai_baseline.py -vv

# Run specific test
pytest tests/services/baseline/test_ai_baseline.py::TestAIServiceBaseline::test_service_initialization -v

# Drop into debugger on failure
pytest tests/services/baseline/test_ai_baseline.py --pdb
```

### Need to Skip Tests Temporarily

```python
@pytest.mark.skip(reason="Known issue - ticket #123")
def test_broken_feature(self):
    pass

# Or skip entire class
@pytest.mark.skip(reason="Service not implemented yet")
class TestNewService:
    pass
```

## Next Steps

### Immediate (This Session)

1. [ ] Analyze actual AI service implementation
2. [ ] Implement AI baseline tests
3. [ ] Analyze actual Cache service implementation
4. [ ] Implement Cache baseline tests
5. [ ] Analyze actual Alert service implementation
6. [ ] Implement Alert baseline tests
7. [ ] Run all tests and ensure 100% passing

### Short Term (Next Session)

8. [ ] Create baseline tests for Flow services
9. [ ] Create baseline tests for Message services
10. [ ] Create baseline tests for Quiz services

### Medium Term (Next Week)

11. [ ] Start Phase 1 consolidations (AI, Cache, Alert)
12. [ ] Run baseline tests after each consolidation
13. [ ] Update consolidated tests in `tests/services/consolidated/`

## Success Criteria

Baseline tests are successful when:

- ✅ **100% of tests pass** before consolidation
- ✅ **Coverage > 80%** for critical services
- ✅ **Performance baselines** documented
- ✅ **Edge cases** covered
- ✅ **Integration scenarios** tested
- ✅ **Tests run in < 5 seconds** (fast feedback)

## Resources

- [QW-017: Consolidation Preparation](../../../REVIEW-2025/QW-017-CONSOLIDATION-PREP.md)
- [QW-016: Services Analysis](../../../REVIEW-2025/QW-016-SERVICES-ANALYSIS.md)
- [Project CHECKLIST](../../../REVIEW-2025/CHECKLIST.md)

---

**Created:** 2025-01-18  
**Status:** 📝 Templates Created - Implementation Needed  
**Coverage:** 0% (templates only)  
**Next:** Analyze services and implement actual tests