# Track Specification: Critical Backend & Flow Fixes

## 1. Overview
This track addresses multiple critical backend errors causing 500 Internal Server Errors and bugs in the Hormonia backend. These errors affect patient timeline retrieval, AI service dependencies, service provider initialization, and flow template management. Additionally, it covers debugging and verification of core business flows: Onboarding, SAGA, and daily WhatsApp accompaniment.

## 2. Issues to Resolve

### 2.1 Timeline Sorting Error (Critical)
*   **Error:** `TypeError: '<' not supported between instances of 'datetime.datetime' and 'str'`
*   **Location:** `app/api/v2/routers/patients/flow.py:357`
*   **Cause:** The `get_patient_timeline` function attempts to sort a list of events where the `date` field is inconsistently typed (some are `datetime` objects, others are `str`).
*   **Goal:** Ensure consistent type handling for event dates before sorting.

### 2.2 Authentication Role Error (High)
*   **Error:** `AttributeError: 'dict' object has no attribute 'role'`
*   **Location:** `app/api/v2/routers/ai/dependencies.py:39` inside `verify_physician_or_admin`
*   **Cause:** The `current_user` object is being returned as a dictionary instead of a Pydantic model or ORM object.
*   **Goal:** Ensure `current_user` is correctly instantiated or update the dependency to handle dictionary access.

### 2.3 Service Injection Error (High)
*   **Error:** `TypeError: PatientCRUDService.__init__() got an unexpected keyword argument 'patient_repository'`
*   **Location:** `app/service_provider.py:247`
*   **Cause:** Argument mismatch between `PatientCRUDService` definition and instantiation.
*   **Goal:** Align the class definition with its instantiation in `ServiceProvider`.

### 2.4 Flow Template Error (High)
*   **Error:** `AttributeError: 'FlowTemplateVersion' object has no attribute 'template_metadata'`
*   **Location:** `app/services/flow_engine.py` (Listing templates)
*   **Cause:** Incorrect attribute access on `FlowTemplateVersion` objects.
*   **Goal:** Correct the attribute access to match the SQLAlchemy model schema.

## 3. Business Flows to Verify
*   **Patient Onboarding:** Creation of patient and triggering of initial flows.
*   **SAGA Flow:** Handling of symptoms and clinical alerts.
*   **WhatsApp Accompaniment:** Daily message delivery logic via Evolution API.

## 4. Functional Requirements
*   **FR-01:** `get_patient_timeline` returns a sorted list of events.
*   **FR-02:** `verify_physician_or_admin` validates user roles without crashing.
*   **FR-03:** `ServiceProvider` initializes `PatientCRUDService` correctly.
*   **FR-04:** Flow templates list correctly without metadata errors.
*   **FR-05:** Core business flows (Onboarding, SAGA, WhatsApp) function end-to-end.

## 5. Acceptance Criteria
*   **AC-01:** `GET /api/v2/patients/{id}/timeline` returns 200 OK and valid JSON.
*   **AC-02:** AI-related protected endpoints succeed for valid users.
*   **AC-03:** `GET /api/v2/templates/flows` returns 200 OK.
*   **AC-04:** Successful execution of a mock/real onboarding and SAGA cycle.
*   **AC-05:** Existing test suite passes.

## 6. Out of Scope
*   New feature development.
*   UI/Frontend styling changes (unless required for debugging).
