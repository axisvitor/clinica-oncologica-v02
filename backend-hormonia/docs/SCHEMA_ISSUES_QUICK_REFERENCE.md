# API Schema Issues - Quick Reference Guide

## Critical Issues Summary (5 Issues - FIX IMMEDIATELY)

| Issue | Router:Line | Schema:Line | Problem | Fix |
|-------|------------|------------|---------|-----|
| 1 | appointments.py:98 | appointment.py:189 | `AppointmentV2List` missing generic type parameter `[AppointmentV2Response]` | Add: `class AppointmentV2List(CursorPaginatedResponse[AppointmentV2Response])` |
| 2 | auth.py:96 | auth.py:462 | `FirebaseTokenVerifyResponse.user` field commented out but returned in response | Uncomment `user: Optional[UserV2Response]` and add Field descriptor |
| 3 | crud.py:70 | patient.py:393 | Router returns dict instead of validated schema instance | Return `PatientV2List(data=..., next_cursor=..., ...)` |
| 4 | auth.py:283 | auth.py:366 | `SessionV2Response.user` missing Field descriptor and validation | Add: `user: Optional[UserV2Response] = Field(None, description="...")` |
| 5 | Multiple | Multiple | DateTime formats inconsistent: examples show timezone sometimes missing, `birth_date` examples use datetime instead of date | Ensure all `datetime` fields serialize with timezone; use `date` type for birth_date |

---

## High Severity Issues (8 Issues - Address in 1-2 Sprints)

| # | Location | Issue | Impact | Priority |
|---|----------|-------|--------|----------|
| 6 | quiz_responses.py:54 | QuizResponseV2List construction bypasses Pydantic validation | Inconsistent optional fields | HIGH |
| 7 | appointment.py:163 | IDs typed as `str` instead of `UUID` | Type unsafe ID comparisons | HIGH |
| 8 | patient.py:388 | Optional relationships not documented per endpoint | Clients don't know when fields exist | HIGH |
| 9 | quiz.py:87 | Field names might not match database model | Data mapping issues | HIGH |
| 10 | dashboard.py:108 | Response type parameters unclear | No type safety | HIGH |
| 11 | Multiple | Missing `Location` header and status code documentation for 201 responses | REST non-compliance | HIGH |
| 12 | appointment.py:189 | `data` vs `items` field naming inconsistency documented but confusing | Client confusion | MEDIUM-HIGH |
| 13 | enhanced_quiz.py:78 | `response_model=Dict[str, Any]` too generic | No client type validation | HIGH |

---

## Medium Severity Issues (6 Issues - Plan for Next Release)

| # | Issue | Recommendation |
|----|-------|-----------------|
| 14 | CREATE vs UPDATE fields not clearly separated in base schema | Create separate Create/Update schemas |
| 15 | Examples violate validation rules | Update all examples to match patterns |
| 16 | Missing descriptions on relationship/metadata fields | Document all fields |
| 17 | `include` parameter allowed values not per-endpoint | Create per-endpoint relationship docs |
| 18 | Eager loading validation incomplete | Document actual available relationships |
| 19 | Field selection no documentation | List allowed fields per endpoint |

---

## File Locations for Quick Fixes

### Must Fix These Files:
1. **app/schemas/v2/auth.py**
   - Line 366: Add Field descriptor to `user`
   - Line 462: Uncomment `user` field in FirebaseTokenVerifyResponse
   - Line 480: Update examples to match schema

2. **app/schemas/v2/appointment.py**
   - Line 189: Change to `class AppointmentV2List(CursorPaginatedResponse[AppointmentV2Response])`
   - Line 163: Change `id: str` → `id: UUID` for all ID fields

3. **app/schemas/v2/patient.py**
   - Line 393: Already correct (has generic type)
   - Line 357: Fix example - remove time from birth_date

4. **app/schemas/v2/common.py**
   - Verify all CursorPaginatedResponse subclasses have type parameters

5. **app/api/v2/routers/auth.py**
   - Line 335: Ensure session/user serialization matches schema

6. **app/api/v2/routers/appointments.py**
   - Line 189: Return PatientV2List instance, not dict

7. **app/api/v2/routers/patients/crud.py**
   - Line 189: Return PatientV2List instance, not dict

---

## Testing Checklist

### Before Deployment
- [ ] All `CursorPaginatedResponse` have type parameters
- [ ] All required Field descriptors present
- [ ] Examples pass Pydantic validation
- [ ] UUID fields consistently typed
- [ ] DateTime examples include timezone info
- [ ] All routers return Pydantic instances (not dicts)
- [ ] Optional relationship fields documented per endpoint
- [ ] No commented-out schema fields in production code

### Integration Tests Needed
```bash
# Test schema validation
pytest tests/schemas/test_auth_schema.py
pytest tests/schemas/test_patient_schema.py
pytest tests/schemas/test_appointment_schema.py

# Test response serialization
pytest tests/api/v2/test_auth_response_serialization.py
pytest tests/api/v2/test_appointment_list_response.py
```

---

## Impact on API Consumers

### Current Problems Clients Face:
1. ❌ TypeScript/Kotlin generation from OpenAPI fails for untyped responses
2. ❌ JSON schema validation fails - can't validate user object structure
3. ❌ Examples in OpenAPI don't match actual schema
4. ❌ No way to know which relationships available per endpoint
5. ❌ Datetime deserialization fails without timezone info
6. ❌ Clients must hardcode UUID format validation

### After Fixes:
1. ✅ Full type safety in generated client libraries
2. ✅ OpenAPI examples match actual responses
3. ✅ Automatic validation on both client and server
4. ✅ Clear API contracts prevent breaking changes
5. ✅ Better IDE autocomplete and intellisense

---

## Breaking Changes Alert

⚠️ **Potential Breaking Changes if Fixed Incorrectly**:

1. `FirebaseTokenVerifyResponse.user` - Currently clients may not expect this field
   - **Mitigation**: Add feature flag or new endpoint version if needed

2. Datetime serialization format - Currently mixed formats in wild
   - **Mitigation**: Accept both formats in parsing, standardize output

3. ID type change `str` → `UUID` - Clients comparing string IDs
   - **Mitigation**: Ensure JSON serialization converts to string for backwards compatibility

---

## OpenAPI Generation Impact

Current issues affect OpenAPI spec generation:

```yaml
# Generated specification issues:
schemas:
  AppointmentV2List:
    properties:
      data: []  # No type specified - should be [AppointmentV2Response]

  FirebaseTokenVerifyResponse:
    properties:
      # Missing user property that examples show!
      valid: boolean
      session_id: string
      # user is NOT in schema but IS in example
```

After fixes:
```yaml
  AppointmentV2List:
    properties:
      data:
        type: array
        items:
          $ref: '#/components/schemas/AppointmentV2Response'  # Proper type

  FirebaseTokenVerifyResponse:
    properties:
      valid: boolean
      session_id: string
      user:
        $ref: '#/components/schemas/UserV2Response'  # Properly documented
```

---

## Rollout Plan

### Phase 1: Foundation (Week 1)
- Fix all critical generic type parameters
- Fix FirebaseTokenVerifyResponse schema
- Update all examples to match validation rules

### Phase 2: Consistency (Week 2)
- Standardize datetime serialization
- Fix ID field typing
- Update response construction to return schema instances

### Phase 3: Documentation (Week 3)
- Document relationships per endpoint
- Create field selection guides
- Update OpenAPI generation

### Phase 4: Validation (Week 4)
- Write comprehensive schema tests
- Test generated client libraries
- Performance testing with validations

---

## Prevention: Add to CI/CD Pipeline

```bash
# Generate and validate OpenAPI spec
pydantic-core validate --schema app/schemas/v2/*.py

# Test all examples pass validation
pytest tests/schemas/test_examples.py

# Check for untyped CursorPaginatedResponse
grep -r "CursorPaginatedResponse[^[]" app/schemas/

# Validate datetime serialization
pytest tests/api/v2/test_datetime_serialization.py
```

---

**Report Generated**: 2025-12-25
**Total Issues Found**: 19 (5 Critical, 8 High, 6 Medium)
**Estimated Fix Time**: 28-40 hours
**Risk Level**: MEDIUM (impacts API consumers)
