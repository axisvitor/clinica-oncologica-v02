"""
Integration Test: Patient Registration Flow End-to-End

Tests the complete patient registration workflow using real database credentials:
1. Patient creation via API
2. Saga orchestration (creation → flow init → messaging)
3. Database validation (foreign keys, constraints)
4. WhatsApp messaging integration

Uses real .env credentials and validates entire saga lifecycle.
"""

import pytest
import time
from datetime import datetime
from uuid import UUID

from app.models.patient import Patient, FlowState
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.enums import SagaStatus
from app.models.flow import PatientFlowState
from app.models.message import Message
from app.schemas.patient import PatientCreate


@pytest.mark.integration
@pytest.mark.asyncio
class TestPatientRegistrationFlow:
    """Test complete patient registration flow with real database."""

    async def test_patient_creation_saga_happy_path(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
        cleanup_flows,
    ):
        """
        Test successful patient registration through saga orchestrator.

        Steps:
        1. Create patient via saga
        2. Validate patient created in DB
        3. Validate saga completed successfully
        4. Validate flow initialized
        5. Validate welcome message scheduled
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")  # Existing doctor
        patient_schema = PatientCreate(**sample_patient_data)

        # Act
        patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        # Assert - Patient created
        assert patient is not None, "Patient should be created"
        assert patient.id is not None
        assert patient.name == sample_patient_data["name"]
        assert patient.doctor_id == doctor_id

        # Track for cleanup
        cleanup_patients.track(patient.id)

        # Validate patient persisted to DB
        db_patient = real_db_session.query(Patient).filter(Patient.id == patient.id).first()
        assert db_patient is not None
        assert db_patient.flow_state in [FlowState.ONBOARDING, FlowState.ACTIVE]

        # Validate saga completed
        sagas = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient.id)
            .all()
        )
        assert len(sagas) >= 1, "Saga record should exist"

        saga = sagas[0]
        cleanup_sagas.track(saga.id)

        # Saga should complete or be at final step
        assert saga.status in [
            SagaStatus.COMPLETED,
            SagaStatus.STEP_4_MESSAGE_SENT,
            SagaStatus.COMPLETED_WITH_WARNINGS,
        ], f"Saga status should be completed, got {saga.status}"

        # Validate execution log
        assert saga.execution_log is not None
        assert len(saga.execution_log) > 0

        # Check step progression
        step_actions = [log["action"] for log in saga.execution_log]
        assert "create_patient" in step_actions
        assert saga.current_step >= 1  # At least patient created

        # Validate flow initialized (if saga reached that step)
        if saga.current_step >= 3:
            flow_states = (
                real_db_session.query(PatientFlowState)
                .filter(PatientFlowState.patient_id == patient.id)
                .all()
            )
            assert len(flow_states) >= 1, "Flow state should be initialized"

            flow_state = flow_states[0]
            cleanup_flows.track(flow_state.id)
            assert flow_state.status in ["onboarding", "active"]

        # Validate message scheduled (if saga reached that step)
        if saga.current_step >= 4:
            messages = (
                real_db_session.query(Message)
                .filter(Message.patient_id == patient.id)
                .all()
            )
            # Message may or may not exist depending on WhatsApp service availability
            # This is a best-effort check
            if messages:
                message = messages[0]
                assert message.message_metadata is not None
                assert message.message_metadata.get("message_type") == "welcome"

    async def test_patient_creation_duplicate_phone_prevention(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test that duplicate phone numbers are prevented at saga level.

        This validates distributed lock and idempotency.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        patient_schema = PatientCreate(**sample_patient_data)

        # Act - Create first patient
        patient1 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        assert patient1 is not None
        cleanup_patients.track(patient1.id)

        # Track saga for cleanup
        saga1 = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient1.id)
            .first()
        )
        if saga1:
            cleanup_sagas.track(saga1.id)

        # Act - Try to create duplicate with same phone
        duplicate_data = sample_patient_data.copy()
        duplicate_data["name"] = "Duplicate Patient"
        duplicate_schema = PatientCreate(**duplicate_data)

        # Should fail due to unique constraint on phone_hash
        patient2 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=duplicate_schema,
            doctor_id=doctor_id,
        )

        # Assert - Second patient creation should fail
        assert patient2 is None, "Duplicate patient creation should fail"

        # Validate saga failure
        failed_sagas = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(
                PatientOnboardingSaga.doctor_id == doctor_id,
                PatientOnboardingSaga.status == SagaStatus.FAILED,
            )
            .order_by(PatientOnboardingSaga.created_at.desc())
            .first()
        )

        if failed_sagas:
            cleanup_sagas.track(failed_sagas.id)
            assert failed_sagas.error_message is not None
            assert failed_sagas.status == SagaStatus.FAILED

    async def test_saga_compensation_on_failure(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
        cleanup_flows,
        monkeypatch,
    ):
        """
        Test saga compensation when a step fails.

        This simulates flow initialization failure and validates rollback.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        patient_schema = PatientCreate(**sample_patient_data)

        # Mock flow service to fail
        original_init = None
        failure_injected = False

        async def mock_initialize_flow_failure(*args, **kwargs):
            nonlocal failure_injected
            failure_injected = True
            raise Exception("Simulated flow initialization failure")

        # Inject failure into flow service
        from app.services.patient import flow_service
        if hasattr(flow_service, 'PatientFlowService'):
            original_init = flow_service.PatientFlowService.initialize_default_flow
            monkeypatch.setattr(
                flow_service.PatientFlowService,
                "initialize_default_flow",
                mock_initialize_flow_failure,
            )

        try:
            # Act
            patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_schema,
                doctor_id=doctor_id,
            )

            # Assert - Patient creation should fail and compensate
            assert patient is None, "Saga should fail and return None"

            # Validate saga failed
            failed_saga = (
                real_db_session.query(PatientOnboardingSaga)
                .filter(PatientOnboardingSaga.doctor_id == doctor_id)
                .order_by(PatientOnboardingSaga.created_at.desc())
                .first()
            )

            assert failed_saga is not None
            cleanup_sagas.track(failed_saga.id)

            assert failed_saga.status == SagaStatus.FAILED
            assert failed_saga.error_message is not None

            # Validate patient was NOT persisted (compensation)
            if failed_saga.patient_id:
                db_patient = (
                    real_db_session.query(Patient)
                    .filter(Patient.id == failed_saga.patient_id)
                    .first()
                )
                # Patient should be deleted by compensation
                assert db_patient is None, "Patient should be rolled back"

        finally:
            # Restore original method
            if original_init:
                monkeypatch.setattr(
                    flow_service.PatientFlowService,
                    "initialize_default_flow",
                    original_init,
                )

    async def test_database_foreign_key_constraints(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test database foreign key constraints are enforced.

        Validates referential integrity.
        """
        # Arrange - Use non-existent doctor ID
        invalid_doctor_id = UUID("00000000-0000-0000-0000-000000000000")
        patient_schema = PatientCreate(**sample_patient_data)

        # Act & Assert - Should fail due to FK constraint
        patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=invalid_doctor_id,
        )

        # Saga should fail
        assert patient is None

        # Validate saga recorded failure
        failed_saga = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.doctor_id == invalid_doctor_id)
            .order_by(PatientOnboardingSaga.created_at.desc())
            .first()
        )

        if failed_saga:
            cleanup_sagas.track(failed_saga.id)
            assert failed_saga.status == SagaStatus.FAILED

    async def test_saga_idempotency(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test saga idempotency with idempotency keys.

        QW-004: Validates duplicate request prevention.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        idempotency_key = f"test_idempotency_{int(time.time() * 1000)}"
        patient_schema = PatientCreate(**sample_patient_data)

        # Act - Create patient with idempotency key
        patient1 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
            idempotency_key=idempotency_key,
        )

        assert patient1 is not None
        cleanup_patients.track(patient1.id)

        # Track saga
        saga1 = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient1.id)
            .first()
        )
        if saga1:
            cleanup_sagas.track(saga1.id)

        # Act - Try to create with same idempotency key
        patient2 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
            idempotency_key=idempotency_key,
        )

        # Assert - Should either return same patient or fail gracefully
        # Depending on implementation, this may return None or same patient
        if patient2:
            assert patient2.id == patient1.id, "Should return same patient for duplicate key"

    async def test_saga_execution_log_completeness(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test saga execution log contains all steps.

        Validates audit trail completeness.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        patient_schema = PatientCreate(**sample_patient_data)

        # Act
        patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        assert patient is not None
        cleanup_patients.track(patient.id)

        # Get saga
        saga = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient.id)
            .first()
        )

        assert saga is not None
        cleanup_sagas.track(saga.id)

        # Validate execution log structure
        assert saga.execution_log is not None
        assert isinstance(saga.execution_log, list)
        assert len(saga.execution_log) > 0

        # Validate each log entry has required fields
        for log_entry in saga.execution_log:
            assert "step" in log_entry
            assert "action" in log_entry
            assert "status" in log_entry
            assert "timestamp" in log_entry

            # Validate timestamp format
            timestamp = datetime.fromisoformat(log_entry["timestamp"])
            assert timestamp is not None

        # Validate expected actions are logged
        actions = [log["action"] for log in saga.execution_log]
        assert "create_patient" in actions

        # Validate all steps are either success or have documented failure
        for log_entry in saga.execution_log:
            assert log_entry["status"] in [
                "success",
                "failed",
                "failed_nonfatal",
                "compensated",
                "compensation_failed",
            ]

    async def test_patient_cascade_deletion(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_sagas,
    ):
        """
        Test cascade deletion of patient and related records.

        Validates ON DELETE CASCADE is working correctly.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        patient_schema = PatientCreate(**sample_patient_data)

        # Act - Create patient
        patient = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        assert patient is not None
        patient_id = patient.id

        # Get related record IDs before deletion
        saga = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.patient_id == patient_id)
            .first()
        )
        saga_id = saga.id if saga else None

        flow_states = (
            real_db_session.query(PatientFlowState)
            .filter(PatientFlowState.patient_id == patient_id)
            .all()
        )
        flow_state_ids = [fs.id for fs in flow_states]

        # Delete patient
        real_db_session.delete(patient)
        real_db_session.commit()

        # Assert - Related records should be cascade deleted

        # Saga should be deleted
        if saga_id:
            remaining_saga = (
                real_db_session.query(PatientOnboardingSaga)
                .filter(PatientOnboardingSaga.id == saga_id)
                .first()
            )
            assert remaining_saga is None, "Saga should be cascade deleted"

        # Flow states should be deleted
        for flow_id in flow_state_ids:
            remaining_flow = (
                real_db_session.query(PatientFlowState)
                .filter(PatientFlowState.id == flow_id)
                .first()
            )
            assert remaining_flow is None, "Flow state should be cascade deleted"

    async def test_concurrent_saga_execution_prevention(
        self,
        real_db_session,
        real_saga_orchestrator,
        sample_patient_data,
        cleanup_patients,
        cleanup_sagas,
    ):
        """
        Test distributed lock prevents concurrent saga execution.

        This is a basic test - true concurrency requires asyncio.gather or threads.
        """
        # Arrange
        doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")
        patient_schema = PatientCreate(**sample_patient_data)

        # Act - Sequential execution (true concurrent test would need asyncio.gather)
        patient1 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        assert patient1 is not None
        cleanup_patients.track(patient1.id)

        # Try again with same phone (should fail due to unique constraint)
        patient2 = await real_saga_orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_schema,
            doctor_id=doctor_id,
        )

        assert patient2 is None, "Duplicate should be prevented"

        # Cleanup sagas
        sagas = (
            real_db_session.query(PatientOnboardingSaga)
            .filter(PatientOnboardingSaga.doctor_id == doctor_id)
            .order_by(PatientOnboardingSaga.created_at.desc())
            .limit(2)
            .all()
        )
        for saga in sagas:
            cleanup_sagas.track(saga.id)
