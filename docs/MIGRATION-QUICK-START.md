# V1 to V2 Migration - Quick Start Guide

**Status:** Analysis Complete | Ready for Implementation
**Total Reducible Code:** 1,512+ lines (12.6% of v1 API)
**Quick Win Timeline:** 1-2 weeks for 777 lines

---

## Key Findings

### Code Duplication Summary
- **Exception Handling:** 450 lines (20+ instances)
- **Pagination:** 180 lines (5+ instances)
- **Validation:** 190 lines (10+ instances)
- **Cache Management:** 150 lines (4+ instances)
- **Audit Logging:** 80 lines (10+ instances)
- **Patient Context:** 80 lines (4+ instances)
- **Response Building:** 150 lines (7+ instances)
- **Authorization:** 60 lines (3+ instances)
- **Analytics Placeholder:** 77 lines (DEAD CODE)

### File Analysis

| File | Lines | Endpoints | Issues | Priority |
|------|-------|-----------|--------|----------|
| flows.py | 1,201 | 38 | Heavy duplication | CRITICAL |
| admin/users.py | 1,179 | 15 | 330 lines reducible | MEDIUM |
| quiz.py | 1,173 | 28 | 457 lines reducible | CRITICAL |
| ai.py | 1,134 | 8 | 400 lines reducible | MEDIUM-HIGH |
| **TOTAL** | **4,687** | **89** | **1,512 lines** | **HIGH** |

---

## Phase 1: Quick Wins (1-2 weeks) - 777 Lines

### 1.1 Remove Analytics Placeholder (77 lines)
**File:** `/backend-hormonia/app/api/v1/quiz.py` (lines 760-836)

**Action:** DELETE
```bash
# Simply delete the get_quiz_summary_analytics function
# All functionality exists in v2/analytics
```

**Impact:** Removes dead code that returns hardcoded empty data

### 1.2 Create Exception Handler Decorator (new file)
**File:** `/backend-hormonia/app/api/v1/decorators.py`

**What to do:**
1. Create decorator `@handle_api_exceptions(endpoint_name)`
2. Extracts identical try-except blocks from 20+ endpoints
3. Apply to all endpoints in flows, quiz, admin/users, ai

**Where it saves:**
- flows.py: 150 lines → 50 lines  
- quiz.py: 200 lines → 50 lines
- admin/users.py: 80 lines → 20 lines
- ai.py: 70 lines → 20 lines

**Total Savings:** 510 lines

### 1.3 Create Validation Utility (new file)
**File:** `/backend-hormonia/app/api/v1/utils/validators.py`

**Functions to create:**
- `validate_name_field(value, field_name)`
- `validate_role(role_string)`
- `validate_question_list(questions)`
- `validate_template_data(name, version, questions)`

**Where it saves:**
- quiz.py: 150 lines
- admin/users.py: 40 lines

**Total Savings:** 190 lines

### 1.4 Create Pagination Utility (new file - Optional Phase 1)
**File:** `/backend-hormonia/app/api/v1/utils/pagination.py`

**Functions to create:**
- `paginate(items, total, page, size) -> dict`
- `PaginatedResponse[T]` generic class

**Where it saves:**
- admin/users.py: 100 lines
- flows.py: 80 lines

**Total Savings:** 180 lines (Move to Phase 2 if time-constrained)

---

## Phase 2: Consolidation (2-4 weeks) - 470 Lines

### 2.1 Consolidate Cache Management (150 lines)
**Current:** v1/ai.py has duplicate Redis utilities (lines 94-168)
**Target:** Use `app/core/redis_unified.py`

**Changes:**
- Remove `get_redis_client()` function
- Remove `get_cached_data()` function  
- Remove `set_cached_data()` function
- Import from unified Redis module instead

### 2.2 Extract Patient Context Builder (80 lines)
**Current:** Repeated 4 times in v1/ai.py
**Create:** `app/api/v1/utils/ai_utils.py`

```python
async def build_patient_context_safely(patient_id, patient_data, ai_service):
    """Safely build patient context with error handling."""
    try:
        return await ai_service.build_patient_context(
            str(patient_id),
            {
                "name": patient_data.name,
                "treatment_type": patient_data.treatment_type or "general",
                "current_day": patient_data.current_day,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to build context: {e}")
        return None
```

### 2.3 Consolidate Audit Logging (80 lines)
**Current:** Manual calls in 10+ endpoints in admin/users.py
**Target:** Use `@audit_action(action_name)` decorator

```python
@router.put("/{user_id}")
@audit_action("update_user")
async def update_user(...):
    # Decorator handles logging automatically
    ...
```

### 2.4 Extract Shared Authorization (60 lines)
**Current:** `verify_physician_or_admin()` defined in both v1 and v2
**Action:** Move to `app/dependencies/auth_overrides.py`
**Files affected:** v1/ai.py, v2/ai.py

---

## Phase 3: Analysis & Planning (4-6 weeks)

### 3.1 Endpoint Deprecation Checklist

For each file, determine V2 equivalent:

**flows.py (38 endpoints)**
- [ ] All endpoints have V2 equivalents
- [ ] V2 versions tested and working
- [ ] Clients identified and contacted
- [ ] Migration path documented

**admin/users.py (15 endpoints)**
- [ ] All endpoints have V2 equivalents
- [ ] V2 versions cover all features
- [ ] Admin tools migrated to V2
- [ ] Deprecation timeline set

**quiz.py (28 endpoints)**
- [ ] Quiz sessions can migrate to V2
- [ ] In-progress sessions can transfer
- [ ] Data migration script prepared
- [ ] V2 analytics implemented

**ai.py (8 endpoints)**
- [ ] V1 chat → V2 humanize mapping
- [ ] All endpoints have equivalents
- [ ] Clinical workflows tested
- [ ] Performance validated

### 3.2 Create Migration Matrix
```markdown
| V1 Endpoint | V2 Endpoint | Status | Clients | Notes |
|-------------|------------|--------|---------|-------|
| /flows/state | /flows/{id} | DUPLICATE | ? | Ready |
| ... | ... | ... | ? | ... |
```

---

## Phase 4: Staged Deprecation (6-12 months)

### Timeline
```
Month 1-2:   Phase 1 & 2 Implementation
Month 3-4:   Add deprecation warnings, publish migration guides
Month 5-6:   Client notification, offer migration support
Month 7-9:   Monitor usage, gather feedback
Month 10-12: Plan sunset (final month)
Month 13-18: Complete removal and archival
```

### Steps
1. Add deprecation headers to v1 responses
2. Log deprecation usage for analytics
3. Provide migration scripts for common patterns
4. Offer transition support
5. Remove endpoints after usage drops below threshold

---

## Implementation Commands

### Phase 1 - Immediate Actions

```bash
# 1. Remove analytics placeholder
cd /backend-hormonia/app/api/v1
vi quiz.py  # Delete lines 760-836

# 2. Create decorators file
cat > decorators.py << 'EOL'
# Add code from Phase 1.2 above
EOL

# 3. Create validators file
mkdir -p utils
cat > utils/validators.py << 'EOL'
# Add code from Phase 1.3 above
EOL

# 4. Run tests
pytest tests/api/v1/ -v
```

### Phase 2 - Consolidation

```bash
# 1. Update imports in v1 files to use utilities
# 2. Apply decorators to endpoints
# 3. Run integration tests
pytest tests/api/v1/ -v

# 4. Measure reduction
wc -l api/v1/*.py  # Before: 4,687 lines
wc -l api/v1/*.py  # After: 2,910 lines (38% reduction)
```

---

## Success Metrics

- [ ] Phase 1: Remove 777 lines (6.4% reduction)
- [ ] Phase 2: Remove 470 lines (cumulative 10.3%)
- [ ] Phase 3: Identify deprecation candidates
- [ ] Phase 4: 50%+ code reduction achieved
- [ ] Zero breaking changes for active clients
- [ ] <5% error rate during migration
- [ ] All migration documented

---

## Risk Mitigation

### Low Risk
- Analytics placeholder removal
- Exception handler extraction
- Validation utilities
- Cache consolidation

### Medium Risk
- Pagination changes
- Authorization consolidation
- Audit logging refactor

### High Risk
- Flow system changes (core to app)
- Quiz session migration (active data)
- User management changes (system critical)

**Recommendation:** Complete Phase 1-2 with low-risk items first

---

## References

- Full Analysis: `/docs/v1-to-v2-migration-analysis.md`
- V1 Source: `/backend-hormonia/app/api/v1/`
- V2 Source: `/backend-hormonia/app/api/v2/`
- Unified Cache: `/backend-hormonia/app/core/redis_unified.py`
- Dependencies: `/backend-hormonia/app/dependencies/`

---

## Next Steps

1. **Review** this guide with the team
2. **Approve** Phase 1 timeline (1-2 weeks)
3. **Assign** ownership (who owns each file)
4. **Start** Phase 1 quick wins
5. **Track** progress with this checklist
6. **Schedule** Phase 2 planning meeting

**Ready to proceed? Comment on PR with approval.**
