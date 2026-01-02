# Implementation Plan - Critical Backend & Flow Fixes

## Phase 1: Fix Service Initialization (PatientCRUDService) [checkpoint: 49c7cf4]
*   [x] Task: Create a reproduction unit test that initializes `ServiceProvider` and requests `patient_service`, verifying the `TypeError`.
*   [x] Task: Analyze `backend-hormonia/app/service_provider.py` and `backend-hormonia/app/services/patient.py` to identify the signature mismatch.
*   [x] Task: Fix the `PatientCRUDService` instantiation or class definition to match arguments.
*   [x] Task: Conductor - User Manual Verification 'Fix Service Initialization (PatientCRUDService)' (Protocol in workflow.md)

## Phase 2: Fix Authentication Role Access
*   [ ] Task: Create a unit test for `verify_physician_or_admin` dependency in `backend-hormonia/app/api/v2/routers/ai/dependencies.py` that mocks `current_user` as a dictionary to reproduce the `AttributeError`.
*   [ ] Task: Modify `verify_physician_or_admin` to handle `current_user` robustly (support both Pydantic models and dictionaries, or ensure consistent type).
*   [ ] Task: Conductor - User Manual Verification 'Fix Authentication Role Access' (Protocol in workflow.md)

## Phase 3: Fix Timeline Sorting (DateTime vs Str)
*   [ ] Task: Create a unit test for `get_patient_timeline` logic in `backend-hormonia/app/api/v2/routers/patients/flow.py` injecting mock data with mixed `datetime` objects and ISO format strings.
*   [ ] Task: Implement a normalization helper or map function to ensure all dates are converted to `datetime` objects (with timezone) before the `sort()` operation.
*   [ ] Task: Conductor - User Manual Verification 'Fix Timeline Sorting (DateTime vs Str)' (Protocol in workflow.md)

## Phase 4: Fix Flow Engine & Templates (SAGA/Onboarding)
*   [ ] Task: Create a reproduction test for fetching flow templates that triggers `AttributeError: 'FlowTemplateVersion' object has no attribute 'template_metadata'`.
*   [ ] Task: Investigate `FlowTemplateVersion` SQLAlchemy model and the query in `get_templates` (or related service). Fix the attribute access.
*   [ ] Task: Conductor - User Manual Verification 'Fix Flow Engine & Templates' (Protocol in workflow.md)

## Phase 5: Debug & Verify Business Flows (Onboarding, SAGA, WhatsApp)
*   [ ] Task: Perform a manual or integration test run of the Patient Onboarding flow (creating a patient, triggering initial flow).
*   [ ] Task: Perform a manual or integration test run of the SAGA flow (triggering symptoms/alerts).
*   [ ] Task: Verify WhatsApp message delivery logs (via Evolution API mock or logs) for the daily accompaniment flow.
*   [ ] Task: Fix any additional logic errors discovered during these flow verifications.
*   [ ] Task: Conductor - User Manual Verification 'Verify Business Flows' (Protocol in workflow.md)

## Phase 6: Final Validation
*   [ ] Task: Run the full backend test suite (`pytest`) to ensure no regressions.
*   [ ] Task: Conductor - User Manual Verification 'Final Validation' (Protocol in workflow.md)
