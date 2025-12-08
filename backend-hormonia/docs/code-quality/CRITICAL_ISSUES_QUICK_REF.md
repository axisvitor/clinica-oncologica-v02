# Critical Code Quality Issues - Quick Reference Card

**Date**: 2025-12-02
**Overall Score**: 6.5/10

---

## 🔴 CRITICAL (Fix Immediately - Week 1-3)

### 1. God Classes - Top 5 Files to Refactor NOW

```
📊 IMPACT: 5,682 lines across 5 files (1.9% of codebase)
⏱️  EFFORT: 180-240 hours
🎯 TARGET: Split each into 3-4 focused classes
```

| File | Lines | Action | Priority | Effort |
|------|-------|--------|----------|--------|
| `patient.py` | 1,015 | Split into 4 repositories | P0 | 40-60h |
| `alert_manager.py` | 915 | Split into 4 services | P0 | 40-50h |
| `physicians.py` | 891 | Extract router logic | P0 | 35-45h |
| `flows.py` (schemas) | 884 | Split by domain | P1 | 30-40h |
| `localization.py` | 876 | Extract translation logic | P1 | 30-40h |

**Quick Win**: Start with `patient.py` - highest complexity + most dependencies

---

### 2. Extreme Complexity Functions

```
📊 IMPACT: 10 functions with complexity > 25
⏱️  EFFORT: 40-60 hours
🎯 TARGET: Reduce all to complexity < 15
```

| Function | Complexity | Location | Fix Strategy |
|----------|------------|----------|--------------|
| `list_v2` | 58 | `repositories/patient.py:153` | Extract QueryBuilder class |
| `validate_patient_data` | 52 | `services/patient/integrity_service.py:56` | Strategy pattern for validators |
| `list_treatments` | 43 | `api/v2/routers/treatments.py:78` | Extract filter logic |
| `list_physicians` | 42 | `api/v2/routers/physicians.py:512` | Use FilterBuilder pattern |

**Quick Win**: Add guard clauses to reduce nesting by 30-40%

---

### 3. Missing Error Logging

```
📊 IMPACT: 20 silent failures in critical paths
⏱️  EFFORT: 8 hours
🎯 TARGET: Add logger.exception() to all catch blocks
```

**Critical Locations**:
```python
# ❌ BAD - Silent failure
except Exception:
    pass  # 💥 Errors disappear!

# ✅ GOOD - Logged failure
except Exception as e:
    logger.exception("Operation failed", extra={"context": context})
    raise
```

**Must Fix**:
- `/app/database.py:144` - DB connection failures
- `/app/integrations/whatsapp/services/evolution_client.py:383` - API errors
- `/app/middleware/query_performance_middleware.py:104` - Query errors

---

## 🟠 HIGH PRIORITY (Fix in Week 4-7)

### 4. Type Safety Crisis

```
📊 COVERAGE: Only 10.1% of functions have return types
⏱️  EFFORT: 80 hours
🎯 TARGET: 80% coverage minimum
```

**Action Plan**:
1. Add return types to all public API endpoints (16h)
2. Add return types to service layer (24h)
3. Add return types to repositories (16h)
4. Enable mypy `--disallow-untyped-defs` gradually (24h)

**Quick Win**: Use IDE auto-complete to add types (saves 50% time)

---

### 5. Optional Types Without None Checks

```
📊 IMPACT: 1,093 potential AttributeError bombs
⏱️  EFFORT: 24 hours
🎯 TARGET: Add None checks or remove Optional
```

**Pattern to Fix**:
```python
# ❌ BAD - Will crash if None
def process(user: Optional[User]):
    return user.email  # 💥 AttributeError if user is None

# ✅ GOOD - Safe access
def process(user: Optional[User]):
    if user is None:
        return None
    return user.email
```

---

### 6. Critical TODOs

```
📊 IMPACT: 6 unimplemented critical features
⏱️  EFFORT: 40 hours
🎯 TARGET: Resolve or create issues with dates
```

| TODO | Location | Impact | Effort |
|------|----------|--------|--------|
| Implement audit table storage | `patient.py:890` | HIGH | 8h |
| Send alerts to monitoring | `webhook_dlq.py:367` | HIGH | 6h |
| Implement email/Slack/SMS | `alert_manager.py:251-291` | HIGH | 16h |
| Batch re-encryption | `encryption.py:780` | MEDIUM | 6h |
| Migrate to DB templates | `flow_automation.py:317` | MEDIUM | 4h |

---

## 🟡 MEDIUM PRIORITY (Fix in Week 8-10)

### 7. Long Functions (>50 Lines)

```
📊 IMPACT: 30 functions that are too long
⏱️  EFFORT: 60 hours
🎯 TARGET: Max 50 lines per function
```

**Top 5 to Refactor**:
- `parse_env_values` (140 lines) → Split into 4 parsers
- `get_public_config` (132 lines) → Extract config builders
- `_check_component_health` (122 lines) → One checker per component
- `_compose_message` (74 lines) → Extract template logic
- `__init__` (61 lines) → Use builder pattern

---

### 8. Magic Numbers

```
📊 IMPACT: 100+ magic numbers scattered throughout
⏱️  EFFORT: 16 hours
🎯 TARGET: Replace with named constants
```

**Quick Fix Pattern**:
```python
# ❌ BAD
task_time_limit = 30 * 60
worker_max_tasks_per_child = 1000

# ✅ GOOD
TASK_TIME_LIMIT_SECONDS = 30 * 60  # 1800 seconds
MAX_TASKS_PER_WORKER = 1000
```

---

### 9. Import Organization

```
📊 IMPACT: 9 files with circular import risk (20+ imports)
⏱️  EFFORT: 16 hours
🎯 TARGET: Max 15 imports per file
```

**Highest Risk Files**:
- `api/v2/router.py` (46 imports) - Use lazy imports
- `models/__init__.py` (28 imports) - Split into submodules
- `services/__init__.py` (27 imports) - Use dependency injection

---

## 📊 Quick Metrics Dashboard

```
┌─────────────────────────────────────────────────────────┐
│ CODE QUALITY SCORECARD                                  │
├─────────────────────────────────────────────────────────┤
│ Overall Score:           6.5/10  [========>  ]  65%    │
│ Security:               9.2/10  [===========>] 92% ✅   │
│ Maintainability:        5.5/10  [======>     ] 55% ⚠️   │
│ Type Safety:            3.0/10  [===>        ] 30% 🔴   │
│ Complexity:             6.0/10  [=======>    ] 60% ⚠️   │
│ Documentation:          8.4/10  [==========> ] 84% ✅   │
└─────────────────────────────────────────────────────────┘
```

**Health Indicators**:
- ✅ **Security**: No eval/exec, no SQL injection, no hardcoded secrets
- ✅ **Logging**: 5,627 logger calls (excellent coverage)
- ✅ **Docstrings**: 84.2% coverage (7,113 / 8,450 functions)
- ⚠️ **File Size**: 143 files > 500 lines (13.5% of codebase)
- ⚠️ **Complexity**: 58 functions with complexity > 10
- 🔴 **Type Hints**: Only 10.1% return type coverage

---

## 🎯 3-Week Sprint Plan (Maximum Impact)

### Week 1: God Classes
**Goal**: Reduce top 3 files from 2,821 → 750 lines (73% reduction)

```bash
# Monday-Wednesday: patient.py (1,015 → 250 lines)
- Extract PatientQueryRepository
- Extract PatientCommandRepository
- Extract PatientSearchRepository
- Extract PatientCacheRepository

# Thursday-Friday: alert_manager.py (915 → 250 lines)
- Extract AlertEvaluator
- Extract AlertProcessor
- Extract AlertNotifier
- Extract AlertStatistics
```

**Deliverable**: 4-8 new focused classes with < 300 lines each

---

### Week 2: Complexity + Error Handling
**Goal**: Fix all complexity > 25 + add logging to critical paths

```bash
# Monday-Tuesday: High complexity functions
- Refactor list_v2 (complexity 58 → 12)
- Refactor validate_patient_data (complexity 52 → 10)
- Refactor list_treatments (complexity 43 → 10)

# Wednesday-Thursday: Error logging
- Add logger.exception() to 20 catch blocks
- Fix database.py silent failures
- Fix evolution_client.py API errors

# Friday: Critical TODOs
- Implement audit table storage (patient.py:890)
- Add monitoring alerts (webhook_dlq.py:367)
```

**Deliverable**: All critical complexity < 15, zero silent failures

---

### Week 3: Type Safety Foundation
**Goal**: Add return types to all public APIs + services

```bash
# Monday-Tuesday: API endpoints (267 async functions)
- Add return types to all v2 routers
- Add return types to WebSocket handlers
- Enable mypy for api/ directory

# Wednesday-Thursday: Service layer (589 sync functions)
- Add return types to all services
- Add return types to all repositories
- Fix Optional[X] without None checks

# Friday: Cleanup
- Run mypy --strict on modified files
- Fix revealed type errors
- Update documentation
```

**Deliverable**: 40-50% type coverage, mypy passing on critical modules

---

## 🚀 Quick Commands for Developers

### Find Your File's Issues
```bash
# Check complexity
radon cc app/path/to/file.py -s

# Check type coverage
mypy app/path/to/file.py --show-error-codes

# Find long functions
grep -n "def " app/path/to/file.py | wc -l

# Count lines
wc -l app/path/to/file.py
```

### Auto-fix Common Issues
```bash
# Format code
black app/path/to/file.py

# Sort imports
isort app/path/to/file.py

# Add type hints (requires pytype)
pytype app/path/to/file.py --output-typeerrors

# Find security issues
bandit app/path/to/file.py
```

### Before Committing
```bash
# Run all quality checks
black app/ && isort app/ && mypy app/ && ruff check app/

# Check complexity
radon cc app/ -a -s -n C  # Fail if avg > C

# Security scan
bandit -r app/ -ll  # Low/Medium/High findings
```

---

## 📋 Definition of Done (Quality Gates)

Before merging ANY PR, ensure:

- [ ] No files > 500 lines (split if needed)
- [ ] No functions > 50 lines (extract if needed)
- [ ] No complexity > 15 (refactor if needed)
- [ ] All new functions have return type hints
- [ ] All new functions have docstrings
- [ ] No `except Exception:` without logging
- [ ] All TODOs have GitHub issues
- [ ] mypy passes with `--strict-optional`
- [ ] ruff/flake8 passes with zero errors
- [ ] Test coverage > 80% for new code

---

## 🎓 Refactoring Patterns Cheat Sheet

### Pattern 1: Split God Class
```python
# Before: 1,015 lines
class PatientRepository:
    def list_v2(...): ...      # 200 lines
    def search(...): ...       # 150 lines
    def create(...): ...       # 100 lines
    # ... 50+ methods

# After: 4 files × 250 lines
class PatientQueryRepository:      # Reads
    def list_v2(...): ...
    def get_by_id(...): ...

class PatientCommandRepository:   # Writes
    def create(...): ...
    def update(...): ...

class PatientSearchRepository:    # Search
    def search(...): ...
    def search_by_email(...): ...

class PatientCacheRepository:     # Caching
    def get_cached(...): ...
    def invalidate(...): ...
```

### Pattern 2: Reduce Complexity with Guards
```python
# Before: Complexity 58
def list_v2(...):
    if filters:
        if 'name' in filters:
            if filters['name']:
                # 50 more lines of nested ifs

# After: Complexity 12
def list_v2(...):
    if not filters:
        return self._list_all()

    if 'name' not in filters:
        return self._list_without_name(filters)

    if not filters['name']:
        return self._list_empty_name(filters)

    return self._list_with_name(filters)
```

### Pattern 3: Extract Strategy
```python
# Before: Complexity 52
def validate_patient_data(data):
    if data.cpf:
        # 10 lines of CPF validation
    if data.email:
        # 10 lines of email validation
    # ... 20 more validations

# After: Complexity 5
class PatientValidator:
    def __init__(self):
        self.validators = [
            CPFValidator(),
            EmailValidator(),
            PhoneValidator(),
            # ...
        ]

    def validate(self, data):
        errors = []
        for validator in self.validators:
            if error := validator.validate(data):
                errors.append(error)
        return errors
```

---

## 💡 Pro Tips

1. **Start with tests**: Write tests BEFORE refactoring (safety net)
2. **Small commits**: Refactor in small, reviewable chunks
3. **Use IDE**: Let your IDE do the heavy lifting (extract method, etc.)
4. **Pair program**: Complex refactors benefit from two sets of eyes
5. **Measure twice**: Run metrics before/after to prove improvement

---

## 📞 Need Help?

**Stuck on a refactoring?** Reference the main report:
- `/docs/code-quality/DEEP_CODE_QUALITY_ANALYSIS.md`

**Want to discuss approach?** Check the roadmap in main report, Phase 1-3

**Tools not working?** See "Recommended Tools & Automation" section

---

**Remember**: Perfect is the enemy of done. Aim for **progress, not perfection**.

Target: **6.5 → 8.5 score in 10 weeks** 🎯
