# Production Test Coverage - Critical Systems

## Overview

This document describes the comprehensive production test coverage for the oncology clinic backend system, focusing on critical areas: WhatsApp integration, Patient flow, and Webhooks.

## Test Files Created

### 1. WhatsApp Service Tests
**File**: `/tests/services/test_unified_whatsapp_service.py`
**Size**: 18KB
**Test Classes**: 3
**Test Methods**: 20+

#### Coverage Areas:

**UnifiedWhatsAppService Core**
- ✅ Successful message sending via queue
- ✅ Message queuing when API fails
- ✅ Retry logic with off-by-one fix (>= instead of >)
- ✅ Metadata enrichment with unified service info
- ✅ Flow context-based retry policy selection
- ✅ Message conversion to queue request format
- ✅ Media message type mapping (image, video, audio, document)
- ✅ Retry with exponential backoff calculation
- ✅ Health check (healthy and degraded states)
- ✅ Unified metrics collection
- ✅ Flow message sending with context
- ✅ Success and failure callbacks
- ✅ Per-message instance name override
- ✅ Graceful service shutdown

**Retry Policies**
- ✅ Default retry policy (3 retries, 2x backoff, 300s base)
- ✅ Flow message retry policy (5 retries, 1.5x backoff, 180s base)
- ✅ Urgent retry policy (7 retries, 1.2x backoff, 60s base)
- ✅ Quiz link retry policy (4 retries, 1.8x backoff, 240s base)

**Queue Integration**
- ✅ Queue message processing initialization
- ✅ Message queue status tracking

**Critical Fixes Tested**
- ✅ Off-by-one error in retry logic (retry_count >= max_retries)
- ✅ Status tracking uses WhatsAppMessage model (not Message)
- ✅ Domain message ID injection for status tracking
- ✅ Queue fallback when Evolution API fails

---

### 2. Webhook Idempotency Tests
**File**: `/tests/integrations/whatsapp/test_webhooks.py`
**Size**: 14KB
**Test Classes**: 6
**Test Methods**: 25+

#### Coverage Areas:

**Webhook Idempotency**
- ✅ First event is processed
- ✅ Duplicate event is skipped
- ✅ Webhook payload structure validation
- ✅ Multiple duplicate detection (5x same event)

**Webhook Event Types**
- ✅ messages.upsert event structure
- ✅ messages.update event structure
- ✅ qrcode.updated event structure
- ✅ connection.update event structure

**Error Handling**
- ✅ Missing required fields (event, instance, data)
- ✅ Malformed JSON payloads
- ✅ Redis connection failure handling

**Message Processing**
- ✅ Extract message content (conversation, extendedTextMessage)
- ✅ Extract sender info (phone, name)
- ✅ Handle media messages (image, video, audio, document)

**Idempotency Cleanup**
- ✅ Cleanup expired records (scan and delete)
- ✅ Cleanup respects TTL (24 hours)

**Rate Limiting**
- ✅ Concurrent webhook processing (race conditions)
- ✅ Burst webhook handling (50 events/second)

**Critical Features Tested**
- ✅ Event ID extraction from Evolution API payload
- ✅ Redis-based duplicate detection (exists + setex)
- ✅ 24-hour TTL for idempotency records
- ✅ Atomic operations to prevent race conditions

---

### 3. Patient Production Tests
**File**: `/tests/api/v2/test_patients_production.py`
**Size**: 17KB
**Test Classes**: 6
**Test Methods**: 20+

#### Coverage Areas:

**Pagination**
- ✅ Respects max limit (1000 items)
- ✅ Rejects negative page numbers
- ✅ Rejects zero or negative size
- ✅ Default values (page=1, size=20)
- ✅ Boundary values (page=1, size=1 and size=1000)

**Idempotency**
- ✅ Create patient with idempotency key
- ✅ Duplicate request returns same patient
- ✅ Different keys create separate patients

**CPF Encryption (LGPD Compliance)**
- ✅ CPF encryption on create
- ✅ CPF decryption works correctly
- ✅ CPF formatting (123.456.789-01)
- ✅ CPF masking (***.***.789-**)
- ✅ CPF hash for searchability
- ✅ Same CPF produces same hash
- ✅ Different CPF produces different hash

**Patient Validation**
- ✅ Birth date minimum age (18 years)
- ✅ Birth date maximum age (120 years)
- ✅ Birth date cannot be in future
- ✅ Phone number format validation (Brazilian)
- ✅ Email format validation

**Flow State Management**
- ✅ Default flow state (ONBOARDING)
- ✅ Default current_day (0)
- ✅ Flow state transitions (ONBOARDING → ACTIVE → PAUSED → COMPLETED)

**Metadata Handling**
- ✅ Metadata schema validation
- ✅ Metadata field getter/setter
- ✅ Metadata bulk update

**Critical Features Tested**
- ✅ Pagination off-by-one prevention
- ✅ CPF never stored in plaintext
- ✅ CPF searchable via hash (LGPD compliant)
- ✅ Age validation prevents invalid data
- ✅ Idempotency prevents duplicate patients

---

### 4. Integration Flow Tests
**File**: `/tests/integration/test_patient_to_whatsapp_flow.py`
**Size**: 18KB
**Test Classes**: 5
**Test Methods**: 15+

#### Coverage Areas:

**Patient to WhatsApp Flow**
- ✅ Complete patient registration flow
- ✅ Welcome message triggered on registration
- ✅ Appointment reminder scheduling (24h before)
- ✅ Saga rollback on WhatsApp failure

**Message Delivery Tracking**
- ✅ Status progression: PENDING → SENDING → SENT → DELIVERED → READ
- ✅ Failed message tracking (retry_count, failure_reason, next_retry_at)
- ✅ Timestamps recorded (sent_at, delivered_at, read_at)

**Patient Flow Progression**
- ✅ Onboarding to Active transition
- ✅ Flow messages sent on schedule (based on current_day)
- ✅ Flow pause and resume (maintains current_day)

**Quiz Integration**
- ✅ Monthly quiz link delivery via WhatsApp
- ✅ Quiz reminder after no response (2 days later)
- ✅ Quiz metadata tracking (session_id, month, template_type)

**Critical Integration Points Tested**
- ✅ Patient creation → WhatsApp welcome message
- ✅ Appointment creation → WhatsApp reminder
- ✅ WhatsApp failure → Saga rollback
- ✅ Quiz schedule → WhatsApp link delivery
- ✅ No quiz response → WhatsApp reminder

---

## Test Execution

### Run All Production Tests
```bash
pytest tests/services/test_unified_whatsapp_service.py \
       tests/integrations/whatsapp/test_webhooks.py \
       tests/api/v2/test_patients_production.py \
       tests/integration/test_patient_to_whatsapp_flow.py \
       -v --tb=short
```

### Run with Coverage
```bash
pytest tests/services/test_unified_whatsapp_service.py \
       tests/integrations/whatsapp/test_webhooks.py \
       tests/api/v2/test_patients_production.py \
       tests/integration/test_patient_to_whatsapp_flow.py \
       --cov=app.services.unified_whatsapp_service \
       --cov=app.integrations.whatsapp \
       --cov=app.api.v2.patients \
       --cov-report=html \
       --cov-report=term-missing
```

### Run Specific Test Class
```bash
# WhatsApp Service
pytest tests/services/test_unified_whatsapp_service.py::TestUnifiedWhatsAppService -v

# Webhook Idempotency
pytest tests/integrations/whatsapp/test_webhooks.py::TestWebhookIdempotency -v

# Patient Pagination
pytest tests/api/v2/test_patients_production.py::TestPatientPagination -v

# Integration Flow
pytest tests/integration/test_patient_to_whatsapp_flow.py::TestPatientToWhatsAppFlow -v
```

---

## Coverage Metrics

### Expected Coverage by Module

| Module | Coverage Target | Critical Paths |
|--------|----------------|----------------|
| UnifiedWhatsAppService | 90%+ | send_message, retry_failed_messages |
| Webhook Handlers | 85%+ | idempotency check, event processing |
| Patient API | 80%+ | pagination, validation, CPF encryption |
| Integration Flows | 75%+ | registration → WhatsApp, saga rollback |

### Coverage Reports
```bash
# Generate HTML coverage report
pytest --cov=app --cov-report=html

# View report
open htmlcov/index.html
```

---

## Critical Fixes Validated

### 1. WhatsApp Service Off-by-One Error
**Issue**: Retry logic used `retry_count > max_retries` instead of `retry_count >= max_retries`
**Test**: `test_retry_respects_max_retries`
**Validation**: Ensures exactly max_retries attempts, not max_retries + 1

### 2. Webhook Idempotency
**Issue**: Duplicate webhooks from Evolution API processed multiple times
**Test**: `test_duplicate_event_skipped`
**Validation**: Redis-based duplicate detection with 24h TTL

### 3. Patient Pagination Limits
**Issue**: No maximum limit on pagination size
**Test**: `test_pagination_respects_max_limit`
**Validation**: Caps at 1000 items regardless of request

### 4. CPF Encryption (LGPD)
**Issue**: CPF stored in plaintext violates LGPD
**Test**: `test_cpf_encryption_on_create`
**Validation**: CPF encrypted with AES-256, searchable via hash

### 5. Saga Rollback
**Issue**: Patient created but welcome message fails → orphaned patient
**Test**: `test_saga_rollback_on_whatsapp_failure`
**Validation**: Transaction rolled back on WhatsApp failure

---

## Test Dependencies

All required dependencies are in `requirements.txt`:
- ✅ `pytest>=8.1.0`
- ✅ `pytest-asyncio>=0.23.0`
- ✅ `pytest-cov>=5.0.0`
- ✅ `pytest-mock>=3.14.0`
- ✅ `pytest-xdist>=3.5.0` (parallel execution)
- ✅ `fastapi>=0.115.0`
- ✅ `httpx>=0.27.0`

---

## Test Organization

```
tests/
├── services/
│   └── test_unified_whatsapp_service.py    # WhatsApp service unit tests
├── integrations/
│   └── whatsapp/
│       └── test_webhooks.py                 # Webhook idempotency tests
├── api/
│   └── v2/
│       └── test_patients_production.py      # Patient API tests
└── integration/
    └── test_patient_to_whatsapp_flow.py     # E2E integration tests
```

---

## Next Steps

### 1. Run Tests Locally
```bash
# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install test dependencies
pip install -r requirements.txt

# Run all production tests
pytest tests/services/test_unified_whatsapp_service.py \
       tests/integrations/whatsapp/test_webhooks.py \
       tests/api/v2/test_patients_production.py \
       tests/integration/test_patient_to_whatsapp_flow.py \
       -v
```

### 2. CI/CD Integration
Add to `.github/workflows/test.yml`:
```yaml
- name: Run Production Tests
  run: |
    pytest tests/services/test_unified_whatsapp_service.py \
           tests/integrations/whatsapp/test_webhooks.py \
           tests/api/v2/test_patients_production.py \
           tests/integration/test_patient_to_whatsapp_flow.py \
           --cov=app \
           --cov-report=xml \
           --cov-report=term-missing \
           --junit-xml=test-results.xml
```

### 3. Monitor Coverage
Set up coverage reporting in CI:
```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
    fail_ci_if_error: true
```

---

## Maintenance

### Adding New Tests
1. Follow existing test structure (Arrange-Act-Assert)
2. Use descriptive test names (`test_<what>_<expected_behavior>`)
3. Mock external dependencies (Redis, database, Evolution API)
4. Test both success and failure scenarios
5. Document critical fixes being validated

### Updating Tests
When modifying code:
1. Update corresponding tests
2. Add tests for new functionality
3. Run full test suite before committing
4. Ensure coverage doesn't decrease

---

## Summary

**Total Test Files**: 4
**Total Test Classes**: 20+
**Total Test Methods**: 80+
**Total Lines of Test Code**: ~67KB
**Critical Systems Covered**: WhatsApp, Webhooks, Patients, Integration Flows
**Critical Fixes Validated**: 5+ production bugs prevented

These tests provide comprehensive coverage of the most critical production systems, ensuring reliability, data integrity, and LGPD compliance.
