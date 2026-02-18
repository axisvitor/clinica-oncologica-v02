---
title: "Implement Cursor Pagination Regression Tests"
labels: ["testing", "pagination", "p1-high", "backend"]
assignees: []
milestone: "Post-Hotfix Stabilization"
---

## 🎯 Objective

Create tests for cursor-based pagination to prevent SQL type errors and pagination bugs in quiz and patient endpoints.

## 📋 Context

**Related PR:** Hotfix - Quiz Cursor Datetime Parsing  
**Fixed in:** `backend-hormonia/app/api/v2/quiz.py:72-82`

The pagination fix prevents Postgres error: `operator does not exist: timestamp without time zone > text`. Without tests, refactoring could reintroduce string comparison bugs.

## ✅ Acceptance Criteria

### Quiz Pagination Tests
- [ ] `test_quiz_pagination_with_cursor` - Test cursor with datetime ISO string parsing
- [ ] `test_quiz_pagination_empty_cursor` - Test first page without cursor
- [ ] `test_quiz_pagination_invalid_cursor` - Test malformed cursor handling (400 error)
- [ ] `test_quiz_pagination_tie_breaking` - Test records with identical created_at timestamps
- [ ] `test_quiz_pagination_descending_order` - Verify newest-first ordering

### Patient Pagination Tests  
- [ ] `test_patients_pagination_with_cursor` - Test patient cursor pagination
- [ ] `test_patients_pagination_no_duplicates` - Verify no duplicate records across pages

### Edge Cases
- [ ] Invalid base64 cursor
- [ ] Valid base64 but invalid JSON
- [ ] Missing required fields (id, created_at)
- [ ] Invalid datetime format in cursor

## 📁 Files to Modify

**Test Files:**
```
backend-hormonia/tests/api/v2/test_quiz_pagination.py
backend-hormonia/tests/api/v2/test_patients.py (add pagination tests)
```

**Fixtures Needed:**
- `create_quiz_sessions(db, patient, count=25)` - Creates multiple quiz sessions
- `create_patients(db, doctor_user, count=25)` - Creates multiple patients
- `auth_token` - Valid authentication token

## 🧪 Test Skeleton

Already created at `backend-hormonia/tests/api/v2/test_quiz_pagination.py` with TODO markers.

## 🔧 Implementation Checklist

- [ ] Implement data creation fixtures (25+ records)
- [ ] Remove `@pytest.mark.skip` from all test methods
- [ ] Test cursor encoding/decoding
- [ ] Test datetime ISO format parsing
- [ ] Test SQL query construction
- [ ] Verify tie-breaking logic (created_at DESC, id ASC)
- [ ] Test both quiz and patient endpoints
- [ ] Add comprehensive edge case coverage
- [ ] Document cursor format in API docs

## 📊 Success Metrics

- All 7 tests passing
- No SQL type errors in any scenario
- No duplicate records across pages
- Cursor base64 decoding handles errors gracefully
- Test execution time < 10 seconds

## 🚨 Critical Bug to Prevent

**SQL Error Scenario:**
```sql
-- Before fix: String comparison causes error
WHERE created_at > '2025-10-18T10:30:00-03:00'  -- ERROR!

-- After fix: Datetime comparison works
WHERE created_at > TIMESTAMP '2025-10-18 10:30:00+00'  -- OK
```

**Test Should Catch:**
```python
# This should NOT throw SQL error
response = client.get(f"/api/v2/quiz?cursor={encoded_cursor}")
assert response.status_code == 200  # Not 500!
```

## 🔗 Related Issues

- Depends on: Hotfix - Cursor Pagination Fix
- Blocks: Production deployment
- Related: #001 (RBAC Tests), #003 (Session Tests)

## ⏱️ Estimated Effort

**6 hours**
- Quiz tests: 2.5 hours
- Patient tests: 1.5 hours
- Edge cases: 1.5 hours
- Documentation: 0.5 hours

## 📝 Notes

- Cursor format: `base64(json({"id": "uuid", "created_at": "iso8601"}))`
- Test with millisecond precision timestamps (tie-breaking)
- Consider testing with empty result sets
- Verify cursor works across page boundaries
- Test maximum limit values (e.g., limit=1000)

## 🔍 Debugging Tips

If tests fail:
1. Decode cursor and inspect JSON structure
2. Check datetime format (ISO 8601 with timezone)
3. Verify SQL query uses proper datetime casting
4. Check for off-by-one errors in tie-breaking logic
