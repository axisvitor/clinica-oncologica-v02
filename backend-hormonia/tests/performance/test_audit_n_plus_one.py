import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.models.user import User
from app.models.quiz import QuizSession, QuizTemplate
from app.repositories.patient import PatientRepository
from app.database import Base
import uuid
import datetime

from app.utils.timezone import now_sao_paulo
class QueryCounter:
    """Helper to count queries during a test block."""
    def __init__(self):
        self.count = 0

    def __call__(self, conn, cursor, statement, parameters, context, executemany):
        # Ignore internal SQLAlchemy queries or migrations
        if "alembic" in statement or "sqlite_master" in statement:
            return
        self.count += 1

@pytest.fixture(autouse=True)
def setup_tables(db_session: Session):
    """Ensure all tables exist in the test database."""
    Base.metadata.create_all(bind=db_session.bind)
    yield

@pytest.mark.performance
class TestNPlusOneAudit:
    """
    Audit verification tests for N+1 query detection and prevention.
    """

    def test_list_patients_n_plus_one(self, db_session: Session):
        """
        Verify that listing patients doesn't trigger N+1 queries for doctors.
        """
        # 1. Setup multiple patients for a doctor
        doctor = User(
            id=uuid.uuid4(),
            email=f"perf_doc_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Perf Doctor",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        for i in range(10):
            p = Patient(
                name=f"Patient {i}",
                doctor_id=doctor.id
            )
            db_session.add(p)
        db_session.commit()

        repo = PatientRepository(db_session)
        counter = QueryCounter()
        
        # 2. Start counting queries
        event.listen(db_session.bind, "before_cursor_execute", counter)
        
        try:
            # 3. Call list_v2 with eager loading
            # We expect: 1 query for count, 1 for main list (with joined doctor)
            results, _, _, _ = repo.list_v2(
                filters={"doctor_id": doctor.id},
                eager_load=["doctor"]
            )
            
            # Access relationship for all patients
            for p in results:
                _ = p.doctor.email
                
            # SQLite joinedload is efficient. Total expected: ~2 queries
            # 1. SELECT count(id)
            # 2. SELECT patients.*, users.* (JOIN)
            assert counter.count <= 3, f"Detected too many queries: {counter.count}. N+1 likely present."
            
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)

    def test_list_patients_with_quizzes_n_plus_one(self, db_session: Session):
        """
        Verify that loading patients with quiz sessions uses selectinload (batch) instead of N+1.
        """
        doctor = User(
            id=uuid.uuid4(),
            email=f"perf_doc_quiz_{uuid.uuid4().hex[:8]}@example.com",
            full_name="Perf Doctor Quiz",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()

        for i in range(5):
            p = Patient(name=f"P {i}", doctor_id=doctor.id)
            db_session.add(p)
            db_session.flush() # Get ID
            
            # Add some quiz sessions with unique templates to avoid uniqueness constraint
            for j in range(2):
                t = QuizTemplate(
                    name=f"Template {i}-{j}",
                    version="1.0",
                    questions=[{"id": "q1", "text": "test"}],
                    is_active=True
                )
                db_session.add(t)
                db_session.flush()

                now = now_sao_paulo()
                qs = QuizSession(
                    patient_id=p.id,
                    quiz_template_id=t.id,
                    status="completed",
                    started_at=now,
                    completed_at=now
                )
                db_session.add(qs)
        
        db_session.commit()

        repo = PatientRepository(db_session)
        counter = QueryCounter()
        
        event.listen(db_session.bind, "before_cursor_execute", counter)
        
        try:
            # Load patients with quiz_sessions
            results, _, _, _ = repo.list_v2(
                filters={"doctor_id": doctor.id},
                eager_load=["quiz_sessions", "doctor"]
            )
            
            # Access relationships for all
            for p in results:
                assert len(p.quiz_sessions) >= 0
                _ = p.doctor.email
            
            # Expected queries:
            # 1. Count
            # 2. Main query (patients JOIN users)
            # 3. selectinload for quiz_sessions (WHERE patient_id IN (...))
            # Total: 3
            assert counter.count <= 4, f"Detected too many queries: {counter.count}. N+1 likely."
            
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)

    def test_get_by_id_eager_loading(self, db_session: Session):
        """
        Verify that get_by_id correctly eager loads relationships.
        """
        doctor = User(
            id=uuid.uuid4(),
            email=f"single_doc_{uuid.uuid4().hex[:8]}@example.com",
            is_active=True
        )
        db_session.add(doctor)
        db_session.commit()
        
        p = Patient(name="Single", doctor_id=doctor.id)
        db_session.add(p)
        db_session.commit()
        
        # Fresh repo with the same session
        repo = PatientRepository(db_session)
        
        # Clear identity map to force reload from DB
        db_session.expire_all()
        
        counter = QueryCounter()
        event.listen(db_session.bind, "before_cursor_execute", counter)
        
        try:
            # repo.get_by_id(id, eager_load=True) uses joinedload(doctor)
            p_loaded = repo.get_by_id(p.id, eager_load=True)
            assert p_loaded is not None
            
            # Access doctor - should NOT trigger new query
            _ = p_loaded.doctor.email
            
            # Total expected: ~3-4
            # 1. Main query (patients JOIN users)
            # 2. selectinload for quiz_sessions
            # 3. selectinload for flow_states
            # (Plus potentially one more for users if joinedload logic differs in SQLite)
            assert counter.count <= 4, f"Expected <= 4 queries, got {counter.count}"
            
        finally:
            event.remove(db_session.bind, "before_cursor_execute", counter)