# QW-020 Phase 5 - Next Steps

**Last Updated**: 2025-01-20  
**Status**: Day 1 Complete ✅ | Day 2-7 Pending

---

## ✅ Completed (Day 1)

### Core Implementation
- [x] Feature flags added (`USE_CONSOLIDATED_ALERTS`, `ALERTS_LEGACY_DEPRECATION_WARNING`)
- [x] Deprecation warnings in `AlertService` and `AlertProcessor`
- [x] API router updated (12 endpoints) with factory pattern
- [x] Celery tasks updated (6 tasks) with factory pattern
- [x] `quiz_flow.py` migrated to use factory pattern

**Files Modified**: 6 files (~300 LOC)

---

## 🎯 Remaining Work

### Day 2: Test Updates & Validation (2-3 hours)

#### Files to Update
1. **Test Files** (~10 files)
   - `tests/services/baseline/test_alert_baseline.py` - Update imports, add feature flag tests
   - `tests/api/test_alerts.py` - Test both legacy and consolidated modes
   - `tests/tasks/test_alerts.py` - Test task switching
   - Other test files importing legacy services

2. **Service Files** (if any remain)
   - Search for: `from app.services.alert import` 
   - Search for: `from app.services.alert_processor import`
   - Update to use factory pattern or feature flag

#### Validation
```bash
# Run full test suite
pytest tests/ -v

# Test with feature flag OFF (legacy)
USE_CONSOLIDATED_ALERTS=False pytest tests/alerts/

# Test with feature flag ON (new)
USE_CONSOLIDATED_ALERTS=True pytest tests/alerts/

# Verify coverage maintained
pytest --cov=app/services --cov-report=html
```

---

### Day 3: Staging Deployment (1-2 hours)

1. **Configuration**
   - Deploy to staging with `USE_CONSOLIDATED_ALERTS=False` (legacy mode)
   - Monitor for 1 hour
   - Enable `USE_CONSOLIDATED_ALERTS=True`
   - Monitor for 4 hours

2. **Monitoring Checklist**
   - [ ] Alert creation rate same as baseline
   - [ ] Alert notification delivery 100%
   - [ ] Escalation processing working
   - [ ] Database performance unchanged
   - [ ] No error rate increase

3. **Rollback Plan**
   - Set `USE_CONSOLIDATED_ALERTS=False`
   - Restart services
   - Verify legacy system operational

---

### Day 4-5: Production Canary (2-3 hours)

1. **10% Rollout** (Day 4 AM)
   - Deploy with feature flag to 10% of servers
   - Monitor for 6 hours
   
2. **50% Rollout** (Day 4 PM)
   - Expand to 50% if 10% successful
   - Monitor for 12 hours

3. **100% Rollout** (Day 5)
   - Full production deployment
   - Monitor for 24 hours

---

### Day 6: Monitoring & Validation (1 hour)

- Review production metrics (24h window)
- Compare performance: old vs new
- Verify zero incidents
- Document any issues found

---

### Day 7: Cleanup (Optional - Phase 6)

**DO NOT DELETE LEGACY CODE YET**

Keep deprecation warnings active for 2 weeks minimum to give developers time to update their code.

After 2 weeks of zero legacy usage:
- Remove legacy `AlertService` 
- Remove legacy `AlertProcessor`
- Remove feature flags
- Update all remaining references

---

## 🔍 Quick Commands

```bash
# Find remaining legacy imports
grep -r "from app.services.alert import" app/ --include="*.py"
grep -r "from app.services.alert_processor import" app/ --include="*.py"

# Run alert tests only
pytest tests/alerts/ tests/services/baseline/test_alert_baseline.py -v

# Check current feature flag status
grep "USE_CONSOLIDATED_ALERTS" .env

# Monitor deprecation warnings
tail -f logs/app.log | grep "DEPRECATED"
```

---

## 📊 Progress Tracking

```
Day 1: Preparation          ████████████████████ 100% ✅
Day 2: Tests & Validation   ░░░░░░░░░░░░░░░░░░░░   0% ← NEXT
Day 3: Staging              ░░░░░░░░░░░░░░░░░░░░   0%
Day 4: Canary 10%→50%       ░░░░░░░░░░░░░░░░░░░░   0%
Day 5: Production 100%      ░░░░░░░░░░░░░░░░░░░░   0%
Day 6: Monitoring           ░░░░░░░░░░░░░░░░░░░░   0%
Day 7: Documentation        ░░░░░░░░░░░░░░░░░░░░   0%
```

**Overall Phase 5**: 14% Complete (Day 1/7)

---

## ⚠️ Critical Reminders

1. **Never delete legacy code during migration** - only deprecate
2. **Always test with both feature flag states** (True/False)
3. **Keep rollback plan ready** - instant rollback via flag
4. **Monitor production closely** - first 48 hours critical
5. **Document any issues immediately** - for retrospective

---

## 📞 Need Help?

- **Rollback**: Set `USE_CONSOLIDATED_ALERTS=False` and restart
- **Issues**: Check logs for deprecation warnings
- **Questions**: See `QW-020-PHASE5-MIGRATION-PLAN.md` for details

---

**Next Session**: Focus on Day 2 - Test updates and validation