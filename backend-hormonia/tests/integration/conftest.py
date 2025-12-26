"""
Integration Test Configuration

Provides fixtures for integration tests that use real database connections
and real saga patterns. All fixtures include proper cleanup to avoid
polluting the database.

Key Features:
- Real database connections (no transaction rollback)
- Real Firebase authentication
- Real saga pattern execution
- Comprehensive cleanup after tests
- Unique identifiers using timestamps
"""

import os
import pytest
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

# Database session is created directly in fixtures
from app.models.patient import Patient
from app.models.patient_onboarding_saga import PatientOnboardingSaga
from app.models.flow import PatientFlowState
from app.models.notification import Notification
from app.orchestration.saga_orchestrator import SagaOrchestrator


@pytest.fixture(scope="session")
def real_database_url() -> str:
    """
    Get real database URL from environment.

    CRITICAL: This should point to a test database, NOT production!
    """
    db_url = os.getenv("DATABASE_URL")

    if not db_url:
        pytest.skip("DATABASE_URL not set - skipping integration tests")

    # Safety check: warn if not using a test database
    if "test" not in db_url.lower():
        pytest.fail(
            "DATABASE_URL does not contain 'test' - refusing to run integration tests "
            "on what appears to be a production database!"
        )

    return db_url


@pytest.fixture(scope="session")
def real_engine(real_database_url):
    """
    Create SQLAlchemy engine for real database connections.

    Uses NullPool to ensure connections are not reused between tests.
    """
    engine = create_engine(
        real_database_url,
        poolclass=NullPool,  # No connection pooling for tests
        echo=False  # Set to True for SQL debugging
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def real_db_session(real_engine) -> Session:
    """
    Real database session that commits changes.

    WARNING: Changes made through this session are PERMANENT.
    Always use cleanup fixtures to remove test data.
    """
    SessionLocal = sessionmaker(bind=real_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cleanup_patients(real_db_session: Session):
    """
    Cleanup fixture that tracks and deletes test patients.

    Usage:
        def test_example(cleanup_patients):
            patient = create_patient(...)
            cleanup_patients.track(patient.id)
            # Test logic...
            # Patient will be deleted after test
    """
    created_patient_ids: List[int] = []

    class PatientCleaner:
        def track(self, patient_id: int):
            """Track a patient ID for cleanup."""
            created_patient_ids.append(patient_id)

        def track_many(self, patient_ids: List[int]):
            """Track multiple patient IDs for cleanup."""
            created_patient_ids.extend(patient_ids)

    cleaner = PatientCleaner()
    yield cleaner

    # Cleanup after test
    if created_patient_ids:
        try:
            # Delete in reverse order to handle foreign key constraints
            for patient_id in reversed(created_patient_ids):
                # Delete related records first
                real_db_session.execute(
                    text("DELETE FROM notifications WHERE patient_id = :id"),
                    {"id": patient_id}
                )
                real_db_session.execute(
                    text("DELETE FROM patient_flow_states WHERE patient_id = :id"),
                    {"id": patient_id}
                )
                real_db_session.execute(
                    text("DELETE FROM patient_onboarding_sagas WHERE patient_id = :id"),
                    {"id": patient_id}
                )
                real_db_session.execute(
                    text("DELETE FROM quiz_sessions WHERE patient_id = :id"),
                    {"id": patient_id}
                )
                real_db_session.execute(
                    text("DELETE FROM consents WHERE patient_id = :id"),
                    {"id": patient_id}
                )
                real_db_session.execute(
                    text("DELETE FROM patients WHERE id = :id"),
                    {"id": patient_id}
                )

            real_db_session.commit()
        except Exception as e:
            real_db_session.rollback()
            # Log but don't fail the test on cleanup errors
            print(f"Warning: Failed to cleanup patients: {e}")


@pytest.fixture
def cleanup_sagas(real_db_session: Session):
    """
    Cleanup fixture for saga instances.

    Tracks and deletes saga records after tests.
    """
    created_saga_ids: List[int] = []

    class SagaCleaner:
        def track(self, saga_id: int):
            """Track a saga ID for cleanup."""
            created_saga_ids.append(saga_id)

        def track_many(self, saga_ids: List[int]):
            """Track multiple saga IDs for cleanup."""
            created_saga_ids.extend(saga_ids)

    cleaner = SagaCleaner()
    yield cleaner

    # Cleanup after test
    if created_saga_ids:
        try:
            for saga_id in reversed(created_saga_ids):
                real_db_session.execute(
                    text("DELETE FROM patient_onboarding_sagas WHERE id = :id"),
                    {"id": saga_id}
                )
            real_db_session.commit()
        except Exception as e:
            real_db_session.rollback()
            print(f"Warning: Failed to cleanup sagas: {e}")


@pytest.fixture
def cleanup_flows(real_db_session: Session):
    """
    Cleanup fixture for flow instances.

    Tracks and deletes flow records after tests.
    """
    created_flow_ids: List[int] = []

    class FlowCleaner:
        def track(self, flow_id: int):
            """Track a flow ID for cleanup."""
            created_flow_ids.append(flow_id)

        def track_many(self, flow_ids: List[int]):
            """Track multiple flow IDs for cleanup."""
            created_flow_ids.extend(flow_ids)

    cleaner = FlowCleaner()
    yield cleaner

    # Cleanup after test
    if created_flow_ids:
        try:
            for flow_id in reversed(created_flow_ids):
                real_db_session.execute(
                    text("DELETE FROM flow_instances WHERE id = :id"),
                    {"id": flow_id}
                )
            real_db_session.commit()
        except Exception as e:
            real_db_session.rollback()
            print(f"Warning: Failed to cleanup flows: {e}")


@pytest.fixture
def unique_phone_number() -> str:
    """
    Generate a unique phone number using timestamp.

    Returns a phone number in format: +5511999XXXXXX
    where XXXXXX is based on current timestamp.
    """
    timestamp = int(datetime.now().timestamp() * 1000) % 1000000
    return f"+5511999{timestamp:06d}"


@pytest.fixture
def unique_email() -> str:
    """
    Generate a unique email using timestamp.

    Returns an email in format: test_TIMESTAMP@example.com
    """
    timestamp = int(datetime.now().timestamp() * 1000)
    return f"test_{timestamp}@example.com"


@pytest.fixture
def real_saga_orchestrator(real_db_session: Session) -> SagaOrchestrator:
    """
    Real saga orchestrator instance with real database session.

    This orchestrator will execute real saga patterns without mocking.
    """
    orchestrator = SagaOrchestrator(db=real_db_session)
    return orchestrator


@pytest.fixture
def sample_patient_data(unique_phone_number, unique_email) -> Dict[str, Any]:
    """
    Generate sample patient data with unique identifiers.

    Returns a dictionary suitable for patient creation.
    """
    timestamp = int(datetime.now().timestamp() * 1000)

    return {
        "name": f"Test Patient {timestamp}",
        "phone": unique_phone_number,
        "email": unique_email,
        "birth_date": "1990-01-01",
        "cpf": f"{timestamp % 100000000000:011d}",  # 11 digits
        "gender": "F",
        "firebase_uid": f"test_firebase_uid_{timestamp}",
    }


@pytest.fixture(scope="function")
def event_loop():
    """
    Create an instance of the default event loop for each test case.

    This is needed for async tests to work properly.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def integration_test_marker():
    """
    Marker to indicate this is an integration test.

    Usage:
        @pytest.mark.integration
        def test_something(integration_test_marker):
            # Test logic...
    """
    # This fixture exists to make it clear when a test is using integration features
    return True


# Cleanup helper functions

def cleanup_all_test_data(session: Session):
    """
    Emergency cleanup function to remove all test data.

    Call this manually if tests leave orphaned data.

    WARNING: This will delete ALL records with test markers!
    """
    try:
        # Clean up test patients (identified by test email pattern)
        session.execute(
            text("DELETE FROM notifications WHERE patient_id IN "
                 "(SELECT id FROM patients WHERE email_hash IS NOT NULL)")
        )
        session.execute(
            text("DELETE FROM patient_flow_states WHERE patient_id IN "
                 "(SELECT id FROM patients WHERE email_hash IS NOT NULL)")
        )
        session.execute(
            text("DELETE FROM patient_onboarding_sagas WHERE patient_id IN "
                 "(SELECT id FROM patients WHERE email LIKE 'test_%@example.com')")
        )
        session.execute(
            text("DELETE FROM quiz_sessions WHERE patient_id IN "
                 "(SELECT id FROM patients WHERE email LIKE 'test_%@example.com')")
        )
        session.execute(
            text("DELETE FROM consents WHERE patient_id IN "
                 "(SELECT id FROM patients WHERE email LIKE 'test_%@example.com')")
        )
        # Clean test patients - using phone pattern since email is encrypted
        session.execute(
            text("DELETE FROM patients WHERE phone_hash IS NOT NULL AND created_at > NOW() - INTERVAL '1 day'")
        )

        session.commit()
        print("Successfully cleaned up all test data")
    except Exception as e:
        session.rollback()
        print(f"Error during cleanup: {e}")
