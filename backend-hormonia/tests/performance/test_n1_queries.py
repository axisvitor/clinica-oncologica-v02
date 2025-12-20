"""
Performance tests to validate N+1 query prevention.

Tests verify that repositories don't trigger N+1 queries when loading
entities with relationships.

Run with: pytest tests/performance/test_n1_queries.py -v
"""
import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from typing import List


class QueryCounter:
    """Helper class to count and track database queries."""

    def __init__(self):
        self.queries: List[str] = []
        self.listener_registered = False

    def start_tracking(self, engine: Engine):
        """Start tracking queries on the given engine."""
        if not self.listener_registered:
            @event.listens_for(engine, "before_cursor_execute")
            def receive_before_cursor_execute(conn, cursor, statement, params, context, executemany):
                self.queries.append(statement)

            self.listener_registered = True

    def reset(self):
        """Reset query counter."""
        self.queries = []

    def count(self) -> int:
        """Get number of queries executed."""
        return len(self.queries)

    def get_queries(self) -> List[str]:
        """Get list of all executed queries."""
        return self.queries


@pytest.fixture
def query_counter(db_session):
    """Fixture to provide query counter for tests."""
    counter = QueryCounter()
    counter.start_tracking(db_session.bind)
    counter.reset()
    yield counter


class TestPatientRepositoryN1:
    """Test Patient Repository for N+1 query patterns."""

    def test_get_all_active_no_n1(self, db_session, query_counter):
        """Verify get_all_active doesn't have N+1 queries."""
        from app.repositories.patient import PatientRepository

        repo = PatientRepository(db_session)
        query_counter.reset()

        # Load 100 patients with relationships
        patients = repo.get_all_active(limit=100, eager_load=True)

        # Should be < 10 queries (1 base + eager loads)
        query_count = query_counter.count()
        assert query_count < 10, f"N+1 detected: {query_count} queries. Expected < 10."

        # Access relationships (should not trigger additional queries)
        initial_count = query_counter.count()
        for patient in patients[:10]:  # Test first 10
            if patient.doctor:
                _ = patient.doctor.name
            _ = list(patient.quiz_sessions)
            _ = list(patient.flow_states)

        # No new queries should be executed
        final_count = query_counter.count()
        assert final_count == initial_count, \
            f"N+1 queries detected on relationship access: {final_count - initial_count} new queries"

    def test_get_by_doctor_no_n1(self, db_session, query_counter, test_doctor):
        """Verify get_by_doctor doesn't have N+1 queries."""
        from app.repositories.patient import PatientRepository

        repo = PatientRepository(db_session)
        query_counter.reset()

        # Load patients for doctor
        patients = repo.get_by_doctor(test_doctor.id, limit=100, eager_load=True)

        # Should be < 10 queries
        query_count = query_counter.count()
        assert query_count < 10, f"N+1 detected: {query_count} queries"

        # Access quiz_sessions and flow_states
        initial_count = query_counter.count()
        for patient in patients[:10]:
            _ = list(patient.quiz_sessions)
            _ = list(patient.flow_states)

        assert query_counter.count() == initial_count, "N+1 queries detected"


class TestQuizRepositoryN1:
    """Test Quiz Repository for N+1 query patterns."""

    def test_get_by_patient_no_n1(self, db_session, query_counter, test_patient):
        """Verify get_by_patient doesn't have N+1 queries."""
        from app.repositories.quiz import QuizRepository

        repo = QuizRepository(db_session)
        query_counter.reset()

        # Load quiz sessions
        sessions = repo.sessions.get_by_patient(test_patient.id, limit=100, eager_load=True)

        # Should be < 5 queries (1 base + 2-3 eager loads)
        query_count = query_counter.count()
        assert query_count < 5, f"N+1 detected: {query_count} queries"

        # Access relationships
        initial_count = query_counter.count()
        for session in sessions[:10]:
            _ = session.patient.name
            _ = session.quiz_template.name

        assert query_counter.count() == initial_count, "N+1 queries detected"

    def test_get_active_sessions_no_n1(self, db_session, query_counter):
        """Verify get_active_sessions doesn't have N+1 queries."""
        from app.repositories.quiz import QuizRepository

        repo = QuizRepository(db_session)
        query_counter.reset()

        # Load active sessions with responses
        sessions = repo.sessions.get_active_sessions(eager_load=True)

        # Should be < 5 queries
        query_count = query_counter.count()
        assert query_count < 5, f"N+1 detected: {query_count} queries"

        # Access all relationships including responses collection
        initial_count = query_counter.count()
        for session in sessions[:10]:
            _ = session.patient.name
            _ = session.quiz_template.name
            _ = list(session.responses)

        assert query_counter.count() == initial_count, "N+1 queries detected"


class TestFlowRepositoryN1:
    """Test Flow Repository for N+1 query patterns."""

    def test_get_by_patient_no_n1(self, db_session, query_counter, test_patient):
        """Verify get_by_patient with nested eager loading."""
        from app.repositories.flow import FlowStateRepository

        repo = FlowStateRepository(db_session)
        query_counter.reset()

        # Load flow states with nested relationships
        flow_states = repo.get_by_patient(test_patient.id, limit=100, eager_load=True)

        # Should be 1 query with nested JOINs
        query_count = query_counter.count()
        assert query_count <= 2, f"N+1 detected: {query_count} queries. Expected 1-2 with nested joins."

        # Access nested relationships
        initial_count = query_counter.count()
        for flow_state in flow_states[:10]:
            _ = flow_state.patient.name
            if flow_state.patient.doctor:
                _ = flow_state.patient.doctor.name
            _ = flow_state.template_version.version
            if flow_state.template_version.kind:
                _ = flow_state.template_version.kind.flow_type

        assert query_counter.count() == initial_count, "N+1 queries detected on nested access"

    def test_get_active_flows_no_n1(self, db_session, query_counter):
        """Verify get_active_flows with nested relationships."""
        from app.repositories.flow import FlowStateRepository

        repo = FlowStateRepository(db_session)
        query_counter.reset()

        # Load active flows
        flow_states = repo.get_active_flows(limit=100, eager_load=True)

        # Should be 1-2 queries
        query_count = query_counter.count()
        assert query_count <= 2, f"N+1 detected: {query_count} queries"

        # Access nested relationships
        initial_count = query_counter.count()
        for flow_state in flow_states[:10]:
            _ = flow_state.patient.name
            if flow_state.patient.doctor:
                _ = flow_state.patient.doctor.name
            _ = flow_state.template_version.version

        assert query_counter.count() == initial_count, "N+1 queries detected"


class TestMedicationRepositoryN1:
    """Test Medication Repository for N+1 query patterns."""

    def test_get_by_patient_no_n1(self, db_session, query_counter, test_patient):
        """Verify get_by_patient doesn't have N+1 queries."""
        from app.repositories.medication import MedicationRepository

        repo = MedicationRepository(db_session)
        query_counter.reset()

        # Load medications
        medications = repo.get_by_patient(test_patient.id, limit=100, eager_load=True)

        # Should be < 5 queries (1 base + 3 eager loads)
        query_count = query_counter.count()
        assert query_count < 5, f"N+1 detected: {query_count} queries"

        # Access all relationships
        initial_count = query_counter.count()
        for medication in medications[:10]:
            _ = medication.patient.name
            if medication.prescribed_by:
                _ = medication.prescribed_by.name
            if medication.treatment:
                _ = medication.treatment.treatment_type

        assert query_counter.count() == initial_count, "N+1 queries detected"

    def test_get_all_no_n1(self, db_session, query_counter):
        """Verify get_all with eager loading."""
        from app.repositories.medication import MedicationRepository

        repo = MedicationRepository(db_session)
        query_counter.reset()

        # Load all medications
        medications = repo.get_all(limit=100, eager_load=True)

        # Should be < 5 queries
        query_count = query_counter.count()
        assert query_count < 5, f"N+1 detected: {query_count} queries"

        # Access relationships
        initial_count = query_counter.count()
        for medication in medications[:10]:
            _ = medication.patient.name
            if medication.prescribed_by:
                _ = medication.prescribed_by.name

        assert query_counter.count() == initial_count, "N+1 queries detected"

    def test_get_active_no_n1(self, db_session, query_counter, test_patient):
        """Verify get_active medications."""
        from app.repositories.medication import MedicationRepository

        repo = MedicationRepository(db_session)
        query_counter.reset()

        # Load active medications
        medications = repo.get_active(patient_id=test_patient.id, limit=100, eager_load=True)

        # Should be < 5 queries
        query_count = query_counter.count()
        assert query_count < 5, f"N+1 detected: {query_count} queries"


class TestAnalyticsServiceN1:
    """Test Analytics Service for N+1 query patterns."""

    @pytest.mark.asyncio
    async def test_calculate_engagement_metrics_no_n1(self, db_session, query_counter):
        """Verify engagement metrics calculation doesn't have N+1 queries."""
        from app.services.flow_analytics import FlowAnalyticsService
        from datetime import datetime, timedelta

        service = FlowAnalyticsService(db_session)
        query_counter.reset()

        # Calculate metrics for last 30 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        metrics = await service.calculate_engagement_metrics(
            flow_type="monthly_quiz",
            date_range=(start_date, end_date)
        )

        # Should be < 20 queries (aggregations + counts)
        query_count = query_counter.count()
        assert query_count < 20, f"N+1 detected in analytics: {query_count} queries"

    @pytest.mark.asyncio
    async def test_identify_at_risk_patients_no_n1(self, db_session, query_counter):
        """Verify at-risk patient identification."""
        from app.services.flow_analytics import FlowAnalyticsService

        service = FlowAnalyticsService(db_session)
        query_counter.reset()

        # Identify at-risk patients
        at_risk = await service.identify_at_risk_patients(
            flow_type="monthly_quiz",
            lookback_days=7
        )

        # Should be < 30 queries for batch analysis
        query_count = query_counter.count()
        assert query_count < 30, f"N+1 detected in risk analysis: {query_count} queries"


class TestPerformanceBenchmarks:
    """Performance benchmarks for query optimization."""

    def test_100_patients_performance(self, db_session, query_counter, benchmark):
        """Benchmark loading 100 patients with relationships."""
        from app.repositories.patient import PatientRepository

        repo = PatientRepository(db_session)

        def load_patients():
            query_counter.reset()
            patients = repo.get_all_active(limit=100, eager_load=True)
            # Access relationships
            for patient in patients[:10]:
                if patient.doctor:
                    _ = patient.doctor.name
            return patients

        # Run benchmark
        result = benchmark(load_patients)

        # Verify performance
        query_count = query_counter.count()
        assert query_count < 10, f"Performance regression: {query_count} queries"

    def test_100_quiz_sessions_performance(self, db_session, query_counter, benchmark, test_patient):
        """Benchmark loading 100 quiz sessions."""
        from app.repositories.quiz import QuizRepository

        repo = QuizRepository(db_session)

        def load_sessions():
            query_counter.reset()
            sessions = repo.sessions.get_patient_sessions(
                test_patient.id,
                limit=100,
                eager_load=True
            )
            # Access relationships
            for session in sessions[:10]:
                _ = session.patient.name
                _ = session.quiz_template.name
                _ = list(session.responses)
            return sessions

        result = benchmark(load_sessions)

        query_count = query_counter.count()
        assert query_count < 5, f"Performance regression: {query_count} queries"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def test_doctor(db_session):
    """Create test doctor."""
    from app.models.user import User

    doctor = User(
        email="test.doctor@example.com",
        name="Dr. Test",
        role="doctor"
    )
    db_session.add(doctor)
    db_session.commit()
    return doctor


@pytest.fixture
def test_patient(db_session, test_doctor):
    """Create test patient."""
    from app.models.patient import Patient

    patient = Patient(
        name="Test Patient",
        email="patient@example.com",
        phone="+5511999999999",
        doctor_id=test_doctor.id
    )
    db_session.add(patient)
    db_session.commit()
    return patient
