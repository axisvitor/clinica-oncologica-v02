---
title: "Implement RBAC Regression Tests for Patient Endpoints"
labels: ["testing", "security", "p0-critical", "backend"]
assignees: []
milestone: "Post-Hotfix Stabilization"
---

## 🎯 Objective

Create comprehensive tests for RBAC patient scoping to prevent privacy regression where doctors could enumerate all patient records.

## 📋 Context

**Related PR:** Hotfix - RBAC Patient List Scoping  
**Fixed in:** `backend-hormonia/app/api/v2/patients.py:113-116`

The RBAC fix prevents doctors from seeing other doctors' patients. Without regression tests, future refactoring could accidentally remove this critical security control.

## ✅ Acceptance Criteria

- [ ] `test_list_patients_rbac_doctor_sees_only_own` - Verify doctors only see their assigned patients
- [ ] `test_list_patients_rbac_admin_sees_all` - Verify admins see all patients regardless of doctor_id
- [ ] `test_get_patient_rbac_doctor_cannot_access_other_patient` - Verify single patient access follows RBAC (404 not 403)
- [ ] `test_get_patient_rbac_doctor_can_access_own` - Verify doctors can access their own patients
- [ ] `test_create_patient_sets_correct_doctor_id` - Verify doctor_id is set to authenticated user
- [ ] `test_update_patient_rbac_doctor_cannot_update_others` - Verify update operations respect RBAC
- [ ] `test_delete_patient_rbac_doctor_cannot_delete_others` - Verify delete operations respect RBAC
- [ ] `test_cursor_pagination_respects_rbac` - Verify paginated results respect RBAC filters
- [ ] All tests pass with 100% coverage on RBAC filter logic
- [ ] Tests run in CI/CD pipeline

## 📁 Files to Modify

**Test File:**
```
backend-hormonia/tests/api/v2/test_patients_rbac.py
```

**Fixtures Needed:**
- `doctor_token(client, doctor_user)` - Returns JWT for doctor
- `admin_token(client, admin_user)` - Returns JWT for admin
- `own_patient(db, doctor_user)` - Creates patient for authenticated doctor
- `other_doctor_patient(db, other_doctor)` - Creates patient for different doctor
- `create_multiple_patients(db, doctor_a, doctor_b)` - Creates 30+ patients for pagination

## 🧪 Test Skeleton

Already created at `backend-hormonia/tests/api/v2/test_patients_rbac.py` with TODO markers.

## 🔧 Implementation Checklist

- [ ] Implement authentication fixtures (JWT generation)
- [ ] Implement patient creation fixtures
- [ ] Remove `@pytest.mark.skip` from all 8 test methods
- [ ] Implement each test case
- [ ] Verify tests fail without RBAC filter (remove filter temporarily)
- [ ] Verify tests pass with RBAC filter
- [ ] Add test to CI/CD pipeline
- [ ] Document any edge cases discovered

## 📊 Success Metrics

- 8/8 tests passing
- Code coverage on `patients.py` RBAC filter > 95%
- Test execution time < 5 seconds
- No false positives/negatives

## 🚨 Critical Security Test

**Attack Scenario to Prevent:**
```bash
# Attacker (Doctor B) tries to enumerate all patients
curl -H "Authorization: Bearer <doctor-b-token>" \
     "https://api.example.com/api/v2/patients?limit=1000"

# Expected: Only returns Doctor B's patients
# Prevented: Returns all patients (privacy breach)
```

## 🔗 Related Issues

- Depends on: #000 (Hotfix - RBAC Patient Scoping)
- Blocks: Deployment to production
- Related: #002 (Cursor Pagination Tests), #003 (Session Tests)

## ⏱️ Estimated Effort

**4 hours**
- Fixtures: 1.5 hours
- Test implementation: 2 hours
- CI/CD integration: 0.5 hours

## 📝 Notes

- Tests should verify 404 (not 403) for unauthorized access to avoid info disclosure
- Consider testing with soft-deleted patients (future enhancement)
- May need to mock Firebase auth for token generation
