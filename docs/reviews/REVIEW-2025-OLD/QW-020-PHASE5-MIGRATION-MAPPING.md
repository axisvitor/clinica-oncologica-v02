# QW-020 Phase 5 Migration - File Mapping

## 📋 Overview

**Date**: 2025-01-20  
**Status**: 🔄 READY TO START  
**Total Files to Update**: 4 main files + tests

---

## 🎯 Files Using Legacy Alert Services

### Analysis Results
```bash
grep -r "from app.services.alert import\|from app.services.alert_processor import\|from app.services.monitoring.alert_service import" backend-hormonia/app/ --include="*.py" -l
```

**Found 4 files**:
1. `backend-hormonia/app/api/v1/alerts.py`
2. `backend-hormonia/app/services/alert_processor.py` (legacy file)
3. `backend-hormonia/app/tasks/alerts.py`
4. `backend-hormonia/app/tasks/quiz_flow.py`

---

## 📝 Detailed Migration Map

### 1. API Router: `app/api/v1/alerts.py`

**Current Imports**:
```python
from app.services.alert import AlertService
from app.services.alert_processor import AlertProcessor
```

**New Imports**:
```python
from app.services.alerts import AlertManager
from app.services.alerts import (
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertRuleType,
    NotificationChannel,
)
```

**Impact**: HIGH - Main API endpoint
**Estimated Time**: 1-2 hours
**Priority**: 🔥 CRITICAL

---

### 2. Legacy Service: `app/services/alert_processor.py`

**Action**: DEPRECATE (add warnings, will be removed later)

**Add Deprecation Warning**:
```python
import warnings

warnings.warn(
    "app.services.alert_processor is deprecated and will be removed in version 3.0. "
    "Use app.services.alerts.AlertProcessor instead. "
    "See migration guide: docs/QW-020-MIGRATION-GUIDE.md",
    DeprecationWarning,
    stacklevel=2
)
```

**Impact**: LOW - Will keep for backward compatibility
**Estimated Time**: 15 minutes
**Priority**: 🟡 MEDIUM

---

### 3. Background Tasks: `app/tasks/alerts.py`

**Current Imports**:
```python
from app.services.alert import AlertService
from app.services.alert_processor import AlertProcessor
```

**New Imports**:
```python
from app.services.alerts import AlertManager
from app.services.alerts import (
    Alert,
    AlertRuleType,
    AlertSeverity,
)
```

**Impact**: HIGH - Celery background tasks
**Estimated Time**: 1-2 hours
**Priority**: 🔥 CRITICAL

---

### 4. Quiz Flow Tasks: `app/tasks/quiz_flow.py`

**Current Imports**:
```python
from app.services.alert import AlertService
```

**New Imports**:
```python
from app.services.alerts import AlertManager
from app.services.alerts import AlertRuleType
```

**Impact**: MEDIUM - Quiz alert triggers
**Estimated Time**: 30 minutes - 1 hour
**Priority**: 🟡 MEDIUM

---

## 🧪 Test Files to Update

### Search for Test Imports
```bash
grep -r "from app.services.alert import\|from app.services.alert_processor import" backend-hormonia/tests/ --include="*.py" -l
```

**Expected Test Files**:
- `tests/api/v1/test_alerts.py`
- `tests/tasks/test_alerts.py`
- `tests/tasks/test_quiz_flow.py`

**Action**: Update imports and fixtures
**Estimated Time**: 1-2 hours total
**Priority**: 🟡 MEDIUM

---

## 🔧 Configuration Updates

### Files to Check/Update

1. **`app/core/dependencies.py`**
   - Add AlertManager dependency injection
   - Estimated Time: 30 minutes

2. **`app/core/config.py`**
   - Add feature flag: `USE_NEW_ALERT_SYSTEM`
   - Estimated Time: 15 minutes

3. **`app/main.py`**
   - Initialize alert system on startup
   - Estimated Time: 30 minutes

---

## 📊 Migration Summary

### Priority Breakdown

**🔥 CRITICAL (Must complete first)**:
- [ ] `app/api/v1/alerts.py` (1-2h)
- [ ] `app/tasks/alerts.py` (1-2h)

**🟡 MEDIUM (Second priority)**:
- [ ] `app/tasks/quiz_flow.py` (30min-1h)
- [ ] `app/services/alert_processor.py` - Add deprecation (15min)
- [ ] Test files (1-2h)

**🟢 LOW (Configuration)**:
- [ ] `app/core/dependencies.py` (30min)
- [ ] `app/core/config.py` (15min)
- [ ] `app/main.py` (30min)

### Total Estimated Time
- **Critical Files**: 2-4 hours
- **Medium Files**: 2-3.5 hours
- **Configuration**: 1-1.5 hours
- **Testing & Validation**: 2-3 hours
- **Total**: **7-11.5 hours** (~1.5 days of work)

---

## ✅ Migration Checklist

### Phase 1: Preparation
- [x] Map all files using legacy services ✅
- [x] Document migration strategy ✅
- [x] Create feature flag plan ✅
- [ ] Review current test baseline
- [ ] Document current metrics

### Phase 2: Core Migration
- [ ] Add feature flag to config
- [ ] Add deprecation warnings to legacy services
- [ ] Update `app/api/v1/alerts.py`
- [ ] Update `app/tasks/alerts.py`
- [ ] Update `app/tasks/quiz_flow.py`

### Phase 3: Configuration
- [ ] Update dependency injection
- [ ] Update startup initialization
- [ ] Add adapter layer (temporary)

### Phase 4: Testing
- [ ] Update test imports
- [ ] Run full test suite
- [ ] Validate all endpoints
- [ ] Performance testing

### Phase 5: Deployment
- [ ] Deploy to staging
- [ ] Smoke tests
- [ ] Monitor for 2-4 hours
- [ ] Deploy to production (gradual rollout)

---

## 🚨 Risk Areas

### High Risk
1. **API Endpoints** (`alerts.py`)
   - Direct user impact
   - Must maintain backward compatibility
   - Mitigation: Feature flag + thorough testing

2. **Background Tasks** (`tasks/alerts.py`)
   - Async processing critical
   - Could cause alert delivery failures
   - Mitigation: Celery task monitoring + rollback plan

### Medium Risk
3. **Quiz Flow** (`quiz_flow.py`)
   - Affects patient engagement
   - Missed alerts could impact care
   - Mitigation: Integration tests + staging validation

### Low Risk
4. **Configuration** (dependencies, config, main)
   - Easy to rollback
   - Clear failure modes
   - Mitigation: Startup health checks

---

## 📈 Success Metrics

### Technical Metrics
- [ ] All 4 main files updated
- [ ] All tests passing (100%)
- [ ] Zero import errors
- [ ] Feature flag working correctly
- [ ] Performance maintained

### Validation Metrics
- [ ] Alert evaluation working
- [ ] Notifications sending
- [ ] Background tasks processing
- [ ] Quiz alerts triggering
- [ ] Escalations functioning

---

## 🔄 Rollback Plan

### Quick Rollback (if needed)
```python
# In app/core/config.py
USE_NEW_ALERT_SYSTEM = False  # Revert to legacy
```

### Files to Revert (if critical issues)
1. Revert `app/api/v1/alerts.py`
2. Revert `app/tasks/alerts.py`
3. Revert `app/tasks/quiz_flow.py`
4. Disable feature flag
5. Restart services

**Rollback Time**: ~15-30 minutes

---

## 📞 Next Actions

### Immediate (Today)
1. ✅ Create this mapping document
2. [ ] Review and validate file list
3. [ ] Set up feature flag
4. [ ] Add deprecation warnings

### Tomorrow
1. [ ] Update API router
2. [ ] Update background tasks
3. [ ] Update quiz flow
4. [ ] Run tests

### Day 3
1. [ ] Deploy to staging
2. [ ] Validate functionality
3. [ ] Monitor metrics
4. [ ] Deploy to production (if stable)

---

## 📚 References

- [Migration Plan](./QW-020-PHASE5-MIGRATION-PLAN.md)
- [Final Summary](./QW-020-FINAL-SUMMARY.md)
- [Phase 4 Complete](../backend-hormonia/docs/QW-020-PHASE4-COMPLETE.md)
- [New Alert System](../backend-hormonia/app/services/alerts/)

---

**Status**: ✅ MAPPING COMPLETE  
**Next Step**: Add feature flag and deprecation warnings  
**Owner**: Backend Development Team  
**Last Updated**: 2025-01-20  
**Version**: 1.0