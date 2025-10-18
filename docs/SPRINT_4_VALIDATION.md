# Sprint 4 - Validation Checklist
## Sistema Hormonia (Clínica Oncológica V02)

**Purpose**: Validar que todas as entregas do Sprint 4 estão funcionando corretamente  
**Last Updated**: January 17, 2025  
**Status**: 🟡 In Progress

---

## 📋 API v2 Validation

### Endpoints Funcionais

#### Patients Endpoints

- [x] **GET /api/v2/patients**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/patients?limit=10" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with paginated list
  ```

- [x] **GET /api/v2/patients/{id}**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/patients/1" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with patient data
  ```

- [x] **POST /api/v2/patients**
  ```bash
  curl -X POST "http://localhost:8000/api/v2/patients" \
    -H "Authorization: Bearer TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "name": "Test Patient",
      "email": "test@example.com",
      "doctor_id": 1
    }'
  
  # Expected: 201 Created
  ```

- [x] **PATCH /api/v2/patients/{id}**
  ```bash
  curl -X PATCH "http://localhost:8000/api/v2/patients/1" \
    -H "Authorization: Bearer TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"phone": "+5511999999999"}'
  
  # Expected: 200 OK with updated data
  ```

- [x] **DELETE /api/v2/patients/{id}**
  ```bash
  curl -X DELETE "http://localhost:8000/api/v2/patients/1" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 204 No Content
  ```

#### Quiz Endpoints

- [x] **GET /api/v2/quiz**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/quiz?limit=10" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with paginated list
  ```

- [x] **GET /api/v2/quiz/{id}**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/quiz/1" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with quiz data
  ```

- [x] **POST /api/v2/quiz**
  ```bash
  curl -X POST "http://localhost:8000/api/v2/quiz" \
    -H "Authorization: Bearer TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "patient_id": 1,
      "month": 1,
      "year": 2025,
      "status": "pending"
    }'
  
  # Expected: 201 Created
  ```

- [x] **PATCH /api/v2/quiz/{id}**
  ```bash
  curl -X PATCH "http://localhost:8000/api/v2/quiz/1" \
    -H "Authorization: Bearer TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"status": "completed"}'
  
  # Expected: 200 OK
  ```

- [x] **DELETE /api/v2/quiz/{id}**
  ```bash
  curl -X DELETE "http://localhost:8000/api/v2/quiz/1" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 204 No Content
  ```

#### Analytics Endpoints

- [x] **GET /api/v2/analytics/overview**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/analytics/overview" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with metrics
  ```

- [x] **GET /api/v2/analytics/quiz-status**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/analytics/quiz-status" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with distribution
  ```

- [x] **GET /api/v2/analytics/completion-trend**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/analytics/completion-trend?months=6" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with trend data
  ```

- [x] **GET /api/v2/analytics/patient-engagement**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/analytics/patient-engagement" \
    -H "Authorization: Bearer TOKEN"
  
  # Expected: 200 OK with engagement metrics
  ```

#### Health Endpoint

- [x] **GET /api/v2/health**
  ```bash
  curl -X GET "http://localhost:8000/api/v2/health"
  
  # Expected: 200 OK
  # {"status": "healthy", "version": "2.0.0", "api": "v2"}
  ```

---

## 🎯 Feature Validation

### Cursor-Based Pagination

- [x] **First Page**
  ```bash
  curl "http://localhost:8000/api/v2/patients?limit=5"
  
  # Expected response:
  {
    "data": [...],
    "next_cursor": "eyJpZCI6NX0=",
    "has_more": true,
    "total": 50
  }
  ```

- [x] **Next Page**
  ```bash
  curl "http://localhost:8000/api/v2/patients?cursor=eyJpZCI6NX0=&limit=5"
  
  # Expected: Next 5 items
  ```

- [x] **Last Page**
  ```bash
  # Keep following next_cursor until has_more = false
  
  # Expected:
  {
    "data": [...],
    "next_cursor": null,
    "has_more": false,
    "total": 50
  }
  ```

### Field Selection

- [x] **Select Specific Fields**
  ```bash
  curl "http://localhost:8000/api/v2/patients?fields=id,name,email"
  
  # Expected: Only id, name, email in response
  {
    "data": [
      {
        "id": 1,
        "name": "João Silva",
        "email": "joao@example.com"
      }
    ]
  }
  ```

- [x] **Invalid Fields**
  ```bash
  curl "http://localhost:8000/api/v2/patients?fields="
  
  # Expected: 400 Bad Request
  # {"error": "ValidationError", "message": "fields cannot be empty"}
  ```

### Eager Loading

- [x] **Include Doctor**
  ```bash
  curl "http://localhost:8000/api/v2/patients/1?include=doctor"
  
  # Expected: Patient with doctor data
  {
    "id": 1,
    "name": "João Silva",
    "doctor": {
      "id": 1,
      "name": "Dr. Maria Santos",
      "crm": "12345-SP"
    }
  }
  ```

- [x] **Include Multiple Relations**
  ```bash
  curl "http://localhost:8000/api/v2/patients/1?include=doctor,quizzes"
  
  # Expected: Patient with doctor and quizzes
  ```

- [x] **Invalid Relation**
  ```bash
  curl "http://localhost:8000/api/v2/patients/1?include=invalid_relation"
  
  # Expected: 400 Bad Request
  # {"error": "ValidationError", "message": "Invalid relations: invalid_relation"}
  ```

### Error Handling

- [x] **404 Not Found**
  ```bash
  curl "http://localhost:8000/api/v2/patients/999999"
  
  # Expected: 404
  # {"error": "NotFound", "message": "Patient with id 999999 not found"}
  ```

- [x] **400 Bad Request**
  ```bash
  curl -X POST "http://localhost:8000/api/v2/patients" \
    -H "Content-Type: application/json" \
    -d '{"name": ""}'
  
  # Expected: 400
  # {"error": "ValidationError", "message": "name cannot be empty"}
  ```

- [x] **409 Conflict**
  ```bash
  # Create patient with existing email
  curl -X POST "http://localhost:8000/api/v2/patients" \
    -H "Content-Type: application/json" \
    -d '{"name": "Test", "email": "existing@example.com", "doctor_id": 1}'
  
  # Expected: 409
  # {"error": "Conflict", "message": "Patient with email existing@example.com already exists"}
  ```

- [x] **401 Unauthorized**
  ```bash
  curl "http://localhost:8000/api/v2/patients"
  # (without Authorization header)
  
  # Expected: 401
  # {"error": "Unauthorized", "message": "Missing or invalid token"}
  ```

---

## 🧪 Test Validation

### Run All Tests

- [x] **Backend Tests**
  ```bash
  cd backend-hormonia
  pytest tests/api/v2/ -v
  
  # Expected: All tests pass
  # test_patients.py::TestPatientsV2::test_list_patients_basic PASSED
  # test_patients.py::TestPatientsV2::test_get_patient_by_id PASSED
  # ... (27 tests total)
  ```

- [x] **Test Coverage**
  ```bash
  pytest tests/api/v2/ --cov=app/api/v2 --cov-report=term
  
  # Expected: 100% coverage for v2 endpoints
  ```

### Individual Test Suites

- [x] **Patients Tests** (15 tests)
  ```bash
  pytest tests/api/v2/test_patients.py -v
  
  # Expected: 15/15 passed
  ```

- [x] **Quiz Tests** (12 tests)
  ```bash
  pytest tests/api/v2/test_quiz.py -v
  
  # Expected: 12/12 passed
  ```

---

## 📚 Documentation Validation

### OpenAPI/Swagger

- [x] **Swagger UI Accessible**
  ```bash
  # Open in browser
  http://localhost:8000/docs
  
  # Expected: Swagger UI loads with v2 endpoints
  ```

- [x] **ReDoc Accessible**
  ```bash
  # Open in browser
  http://localhost:8000/redoc
  
  # Expected: ReDoc loads with v2 endpoints
  ```

- [x] **OpenAPI JSON**
  ```bash
  curl http://localhost:8000/openapi.json
  
  # Expected: Valid OpenAPI 3.0 spec
  ```

### Schema Documentation

- [x] **Schemas Have Descriptions**
  ```python
  # Check in code
  # app/schemas/v2/patient.py
  
  class PatientV2Create(BaseModel):
      name: str = Field(..., description="Patient full name")
      email: EmailStr = Field(..., description="Patient email address")
      # ...
  ```

- [x] **Schemas Have Examples**
  ```python
  class Config:
      schema_extra = {
          "example": {
              "name": "João Silva",
              "email": "joao@example.com"
          }
      }
  ```

### Endpoint Documentation

- [x] **Endpoints Have Summaries**
  ```python
  @router.get(
      "",
      summary="List patients with pagination",
      description="Get paginated list of patients..."
  )
  ```

- [x] **Endpoints Have Examples**
  ```python
  # Check in Swagger UI
  # Each endpoint should have request/response examples
  ```

---

## 🔧 Integration Validation

### Router Registration

- [x] **v2 Router Registered**
  ```python
  # Check in app/core/router_registry.py
  
  from app.api.v2 import api_v2_router
  app.include_router(api_v2_router, tags=["API v2"])
  ```

- [x] **v2 Endpoints Accessible**
  ```bash
  curl http://localhost:8000/api/v2/health
  
  # Expected: 200 OK
  ```

### Backward Compatibility

- [x] **v1 Still Works**
  ```bash
  curl http://localhost:8000/api/v1/patients
  
  # Expected: 200 OK (v1 response format)
  ```

- [x] **Both Versions Coexist**
  ```bash
  # v1
  curl http://localhost:8000/api/v1/patients
  
  # v2
  curl http://localhost:8000/api/v2/patients
  
  # Expected: Both work independently
  ```

---

## 🚀 Performance Validation

### Response Times

- [ ] **p50 < 100ms**
  ```bash
  # Use Apache Bench
  ab -n 1000 -c 10 http://localhost:8000/api/v2/patients
  
  # Check: 50% of requests < 100ms
  ```

- [ ] **p95 < 200ms**
  ```bash
  # Check: 95% of requests < 200ms
  ```

- [ ] **p99 < 500ms**
  ```bash
  # Check: 99% of requests < 500ms
  ```

### Payload Sizes

- [x] **Field Selection Reduces Size**
  ```bash
  # Full response
  curl http://localhost:8000/api/v2/patients/1 | wc -c
  # Example: 700 bytes
  
  # With field selection
  curl "http://localhost:8000/api/v2/patients/1?fields=id,name,email" | wc -c
  # Example: 200 bytes (71% reduction)
  ```

### Query Optimization

- [x] **No N+1 Queries**
  ```bash
  # Enable SQL logging
  # Check logs for multiple SELECT queries
  
  # Without eager loading: N+1 queries
  curl http://localhost:8000/api/v2/patients
  # Expected: 1 query for patients + N queries for doctors
  
  # With eager loading: 1 query
  curl "http://localhost:8000/api/v2/patients?include=doctor"
  # Expected: 1 query with JOIN
  ```

---

## 🔒 Security Validation

### Authentication

- [x] **Requires Auth Token**
  ```bash
  curl http://localhost:8000/api/v2/patients
  
  # Expected: 401 Unauthorized
  ```

- [x] **Accepts Valid Token**
  ```bash
  curl -H "Authorization: Bearer VALID_TOKEN" \
    http://localhost:8000/api/v2/patients
  
  # Expected: 200 OK
  ```

- [x] **Rejects Invalid Token**
  ```bash
  curl -H "Authorization: Bearer INVALID_TOKEN" \
    http://localhost:8000/api/v2/patients
  
  # Expected: 401 Unauthorized
  ```

### Input Validation

- [x] **SQL Injection Protected**
  ```bash
  curl "http://localhost:8000/api/v2/patients?search='; DROP TABLE patients; --"
  
  # Expected: Safe (parameterized queries)
  ```

- [x] **XSS Protected**
  ```bash
  curl -X POST http://localhost:8000/api/v2/patients \
    -H "Content-Type: application/json" \
    -d '{"name": "<script>alert(1)</script>", "email": "test@example.com"}'
  
  # Expected: Sanitized or rejected
  ```

---

## ✅ Acceptance Criteria

### Must Have (P0)

- [x] All 15 v2 endpoints functional
- [x] Cursor pagination working
- [x] Field selection working
- [x] Eager loading working
- [x] 27 tests passing
- [x] 100% test coverage for v2
- [x] OpenAPI docs generated
- [x] Backward compatibility with v1

### Should Have (P1)

- [ ] Rate limiting configured
- [ ] Performance benchmarks completed
- [ ] Redis caching implemented
- [ ] Monitoring dashboards created

### Nice to Have (P2)

- [ ] GraphQL support
- [ ] WebSocket support
- [ ] Batch operations

---

## 📊 Quality Gates

### Code Quality

- [x] **No Linter Errors**
  ```bash
  ruff check app/api/v2/
  # Expected: 0 errors
  ```

- [x] **No Type Errors**
  ```bash
  mypy app/api/v2/
  # Expected: 0 errors
  ```

- [x] **No Security Issues**
  ```bash
  bandit -r app/api/v2/
  # Expected: 0 high/medium issues
  ```

### Test Quality

- [x] **All Tests Pass**
  ```bash
  pytest tests/api/v2/ -v
  # Expected: 27/27 passed
  ```

- [x] **100% Coverage**
  ```bash
  pytest tests/api/v2/ --cov=app/api/v2 --cov-report=term
  # Expected: 100%
  ```

- [x] **No Flaky Tests**
  ```bash
  # Run tests 10 times
  for i in {1..10}; do pytest tests/api/v2/; done
  # Expected: All runs pass
  ```

---

## 🎉 Sign-Off

### Team Validation

- [x] **Backend Team**: API v2 implemented and tested
- [ ] **Frontend Team**: Ready to integrate v2
- [ ] **QA Team**: Smoke tests passed
- [ ] **DevOps Team**: Deployment ready
- [ ] **Product Owner**: Acceptance criteria met

### Deployment Readiness

- [x] **Staging Deployed**: Yes
- [ ] **Staging Validated**: Pending
- [ ] **Production Ready**: Pending
- [ ] **Rollback Plan**: Documented

---

**Validation Status**: 🟢 85% Complete  
**Next Steps**: Complete performance testing and monitoring setup  
**Target Completion**: End of Day 2

---

**Document Version**: 1.0  
**Created**: January 17, 2025  
**Owner**: QA Team  
**Status**: ✅ Active
