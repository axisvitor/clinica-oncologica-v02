"""
RLS (Row Level Security) Policy Tests

Tests to verify that RLS policies are correctly enforcing data isolation:
- Doctors can only see their own patients
- Medical reports are isolated by doctor
- Quiz responses are accessible by owning doctor
- Users can only update their own profile
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.patient import Patient
from app.core.database_direct import execute_sql


@pytest.fixture
async def doctor1_context(async_db_session: AsyncSession):
    """
    Create a doctor user and set Firebase JWT context for RLS.

    Simulates a request with Firebase JWT claims.
    """
    # Create doctor1
    doctor1 = User(
        email="doctor1.rls.test@clinic.com",
        full_name="Dr. RLS Test 1",
        role="doctor",
        firebase_uid="test_firebase_uid_doctor1"
    )
    async_db_session.add(doctor1)
    await async_db_session.commit()
    await async_db_session.refresh(doctor1)

    # Set JWT context for RLS (simulating Firebase auth)
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor1"}'}
    )

    yield doctor1

    # Cleanup
    await async_db_session.delete(doctor1)
    await async_db_session.commit()


@pytest.fixture
async def doctor2_context(async_db_session: AsyncSession):
    """Create a second doctor user with different Firebase UID"""
    doctor2 = User(
        email="doctor2.rls.test@clinic.com",
        full_name="Dr. RLS Test 2",
        role="doctor",
        firebase_uid="test_firebase_uid_doctor2"
    )
    async_db_session.add(doctor2)
    await async_db_session.commit()
    await async_db_session.refresh(doctor2)

    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor2"}'}
    )

    yield doctor2

    await async_db_session.delete(doctor2)
    await async_db_session.commit()


@pytest.mark.asyncio
async def test_doctor_can_only_see_own_patients(
    async_db_session: AsyncSession,
    doctor1_context: User,
    doctor2_context: User
):
    """
    Test: Doctors should only see patients they created

    RLS Policy: patients_select_own_doctor
    """
    # Create patient for doctor1
    patient1 = Patient(
        name="Patient RLS 1",
        phone="11999000001",
        email="patient1@test.com",
        doctor_id=doctor1_context.id,
        flow_state="active",
        current_day=1
    )
    async_db_session.add(patient1)

    # Create patient for doctor2
    patient2 = Patient(
        name="Patient RLS 2",
        phone="11999000002",
        email="patient2@test.com",
        doctor_id=doctor2_context.id,
        flow_state="active",
        current_day=1
    )
    async_db_session.add(patient2)
    await async_db_session.commit()

    # Set context as doctor1
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor1"}'}
    )

    # Query patients as doctor1
    result = await async_db_session.execute(
        text("SELECT id, name FROM patients")
    )
    patients_doctor1 = result.fetchall()

    # Doctor1 should see only patient1
    assert len(patients_doctor1) == 1, "Doctor1 should see exactly 1 patient"
    assert patients_doctor1[0][1] == "Patient RLS 1", "Doctor1 should see their own patient"

    # Set context as doctor2
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor2"}'}
    )

    # Query patients as doctor2
    result = await async_db_session.execute(
        text("SELECT id, name FROM patients")
    )
    patients_doctor2 = result.fetchall()

    # Doctor2 should see only patient2
    assert len(patients_doctor2) == 1, "Doctor2 should see exactly 1 patient"
    assert patients_doctor2[0][1] == "Patient RLS 2", "Doctor2 should see their own patient"

    # Cleanup
    await async_db_session.delete(patient1)
    await async_db_session.delete(patient2)
    await async_db_session.commit()


@pytest.mark.asyncio
async def test_user_can_only_update_own_profile(async_db_session: AsyncSession):
    """
    Test: Users can only update their own profile

    RLS Policy: users_update_own
    """
    # Create two users
    user1 = User(
        email="user1.update.test@test.com",
        full_name="User Update Test 1",
        role="doctor",
        firebase_uid="test_update_uid_1"
    )
    user2 = User(
        email="user2.update.test@test.com",
        full_name="User Update Test 2",
        role="doctor",
        firebase_uid="test_update_uid_2"
    )
    async_db_session.add_all([user1, user2])
    await async_db_session.commit()
    await async_db_session.refresh(user1)
    await async_db_session.refresh(user2)

    # Set context as user1
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_update_uid_1"}'}
    )

    # Try to update user1's own profile (should succeed)
    result = await async_db_session.execute(
        text("""
        UPDATE users
        SET full_name = 'Updated Name 1'
        WHERE id = :user_id
        RETURNING id;
        """),
        {"user_id": str(user1.id)}
    )
    updated_rows = result.fetchall()
    assert len(updated_rows) == 1, "User1 should be able to update their own profile"

    # Try to update user2's profile (should fail/return 0 rows due to RLS)
    result = await async_db_session.execute(
        text("""
        UPDATE users
        SET full_name = 'Hacked Name 2'
        WHERE id = :user_id
        RETURNING id;
        """),
        {"user_id": str(user2.id)}
    )
    updated_rows = result.fetchall()
    assert len(updated_rows) == 0, "User1 should NOT be able to update user2's profile"

    # Verify user2's profile was NOT changed
    await async_db_session.refresh(user2)
    assert user2.full_name == "User Update Test 2", "User2's profile should remain unchanged"

    # Cleanup
    await async_db_session.delete(user1)
    await async_db_session.delete(user2)
    await async_db_session.commit()


@pytest.mark.asyncio
async def test_medical_reports_isolated_by_doctor(
    async_db_session: AsyncSession,
    doctor1_context: User,
    doctor2_context: User
):
    """
    Test: Medical reports are only visible to the doctor who owns the patient

    RLS Policy: medical_reports_select_own_patients
    """
    from app.models.medical_report import MedicalReport

    # Create patients
    patient1 = Patient(
        name="Patient Report 1",
        phone="11999000011",
        email="patient.report1@test.com",
        doctor_id=doctor1_context.id,
        flow_state="active",
        current_day=1
    )
    patient2 = Patient(
        name="Patient Report 2",
        phone="11999000022",
        email="patient.report2@test.com",
        doctor_id=doctor2_context.id,
        flow_state="active",
        current_day=1
    )
    async_db_session.add_all([patient1, patient2])
    await async_db_session.commit()
    await async_db_session.refresh(patient1)
    await async_db_session.refresh(patient2)

    # Create medical reports
    report1 = MedicalReport(
        patient_id=patient1.id,
        report_type="diagnosis",
        content="Diagnosis for patient 1",
        generated_by="AI"
    )
    report2 = MedicalReport(
        patient_id=patient2.id,
        report_type="diagnosis",
        content="Diagnosis for patient 2",
        generated_by="AI"
    )
    async_db_session.add_all([report1, report2])
    await async_db_session.commit()

    # Set context as doctor1
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor1"}'}
    )

    # Query reports as doctor1
    result = await async_db_session.execute(
        text("SELECT id, content FROM medical_reports")
    )
    reports_doctor1 = result.fetchall()

    # Doctor1 should see only report1
    assert len(reports_doctor1) == 1, "Doctor1 should see exactly 1 report"
    assert "patient 1" in reports_doctor1[0][1], "Doctor1 should see their patient's report"

    # Set context as doctor2
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "test_firebase_uid_doctor2"}'}
    )

    # Query reports as doctor2
    result = await async_db_session.execute(
        text("SELECT id, content FROM medical_reports")
    )
    reports_doctor2 = result.fetchall()

    # Doctor2 should see only report2
    assert len(reports_doctor2) == 1, "Doctor2 should see exactly 1 report"
    assert "patient 2" in reports_doctor2[0][1], "Doctor2 should see their patient's report"

    # Cleanup
    await async_db_session.delete(report1)
    await async_db_session.delete(report2)
    await async_db_session.delete(patient1)
    await async_db_session.delete(patient2)
    await async_db_session.commit()


@pytest.mark.asyncio
async def test_quiz_templates_accessible_to_authenticated_users(async_db_session: AsyncSession):
    """
    Test: Quiz templates should be readable by all authenticated users

    RLS Policy: quiz_templates_select_authenticated
    """
    from app.models.quiz import QuizTemplate

    # Create a quiz template (as admin/system)
    quiz = QuizTemplate(
        name="RLS Test Quiz",
        version="1.0",
        questions={"questions": []}
    )
    async_db_session.add(quiz)
    await async_db_session.commit()
    await async_db_session.refresh(quiz)

    # Set context as authenticated user (any firebase_uid)
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', :jwt_claims, true);
        """),
        {"jwt_claims": '{"sub": "any_authenticated_user"}'}
    )

    # Query quiz templates
    result = await async_db_session.execute(
        text("SELECT id, name FROM quiz_templates WHERE id = :quiz_id"),
        {"quiz_id": str(quiz.id)}
    )
    quizzes = result.fetchall()

    # Should be able to read
    assert len(quizzes) == 1, "Authenticated user should see quiz template"
    assert quizzes[0][1] == "RLS Test Quiz"

    # Cleanup
    await async_db_session.delete(quiz)
    await async_db_session.commit()


@pytest.mark.asyncio
async def test_unauthenticated_access_denied(async_db_session: AsyncSession):
    """
    Test: Unauthenticated requests should not access protected tables

    This simulates a request without Firebase JWT
    """
    # Clear JWT context (simulate unauthenticated request)
    await async_db_session.execute(
        text("""
        SELECT set_config('request.jwt.claims', NULL, true);
        """)
    )

    # Try to query patients (should return 0 rows due to RLS)
    result = await async_db_session.execute(
        text("SELECT id FROM patients")
    )
    patients = result.fetchall()

    assert len(patients) == 0, "Unauthenticated request should see no patients"

    # Try to query users (should return 0 rows due to RLS)
    result = await async_db_session.execute(
        text("SELECT id FROM users")
    )
    users = result.fetchall()

    assert len(users) == 0, "Unauthenticated request should see no users"
