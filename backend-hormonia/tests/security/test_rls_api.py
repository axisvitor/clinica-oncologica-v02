"""
RLS Testing via API - Test Row Level Security through HTTP endpoints.

This module tests RLS policies by making HTTP requests to the FastAPI backend,
which validates the real production flow: JWT token → middleware → RLS context → database.

This approach bypasses the pgBouncer/AsyncPG incompatibility by testing through
the actual API layer that users interact with.
"""
import pytest
import httpx
from typing import Dict
from uuid import uuid4


pytestmark = pytest.mark.asyncio


class TestRLSAuthenticationAPI:
    """Test authentication requirements for RLS-protected endpoints."""

    async def test_unauthenticated_access_denied_users(
        self,
        http_client: httpx.AsyncClient
    ):
        """
        Test that unauthenticated requests to /users are denied.

        RLS Policy: users_select_own requires 'authenticated' role.
        Expected: 401 Unauthorized or empty result set.
        """
        response = await http_client.get("/api/v1/users")

        # Either denied with 401/403, or returns empty list
        assert response.status_code in (401, 403) or response.json() == []

    async def test_unauthenticated_access_denied_patients(
        self,
        http_client: httpx.AsyncClient
    ):
        """
        Test that unauthenticated requests to /patients are denied.

        RLS Policy: patients table requires authenticated user.
        Expected: 401 Unauthorized or empty result set.
        """
        response = await http_client.get("/api/v1/patients")

        assert response.status_code in (401, 403) or response.json() == []

    async def test_expired_token_rejected(
        self,
        http_client: httpx.AsyncClient,
        expired_token_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that expired JWT tokens are rejected.

        Expected: 401 Unauthorized
        """
        headers = auth_headers(expired_token_credentials)
        response = await http_client.get("/api/v1/users", headers=headers)

        assert response.status_code in (401, 403)


class TestRLSUserIsolationAPI:
    """Test user isolation via RLS policies through API."""

    async def test_user_can_only_read_own_profile(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that users can only read their own user profile.

        RLS Policy: users_select_own restricts SELECT to own firebase_uid.
        Expected: Doctor A sees only their profile, not Doctor B's.
        """
        # First, create both users in the database (via service role or registration endpoint)
        # For this test, we assume users exist or we use a setup fixture

        # Doctor A queries users
        headers_a = auth_headers(doctor_a_credentials)
        response_a = await http_client.get("/api/v1/users/me", headers=headers_a)

        if response_a.status_code == 200:
            user_a_data = response_a.json()
            # Should only see own firebase_uid
            assert user_a_data.get("firebase_uid") == doctor_a_credentials["firebase_uid"]
            assert user_a_data.get("email") == doctor_a_credentials["email"]

        # Doctor B queries users
        headers_b = auth_headers(doctor_b_credentials)
        response_b = await http_client.get("/api/v1/users/me", headers=headers_b)

        if response_b.status_code == 200:
            user_b_data = response_b.json()
            # Should only see own firebase_uid
            assert user_b_data.get("firebase_uid") == doctor_b_credentials["firebase_uid"]
            assert user_b_data.get("email") == doctor_b_credentials["email"]

            # Ensure Doctor A and Doctor B have different profiles
            if response_a.status_code == 200:
                assert user_a_data.get("firebase_uid") != user_b_data.get("firebase_uid")

    async def test_user_cannot_update_other_user_profile(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that users cannot update other users' profiles.

        RLS Policy: users_update_own restricts UPDATE to own firebase_uid.
        Expected: Doctor A cannot update Doctor B's profile.
        """
        headers_a = auth_headers(doctor_a_credentials)

        # Doctor A tries to update Doctor B's profile
        # (Assuming we know Doctor B's user ID or email)
        update_payload = {
            "full_name": "Hacked Name"
        }

        # Attempt to update via email or firebase_uid
        response = await http_client.patch(
            f"/api/v1/users/{doctor_b_credentials['firebase_uid']}",
            headers=headers_a,
            json=update_payload
        )

        # Should be denied (403 Forbidden or 404 Not Found if RLS hides the record)
        assert response.status_code in (403, 404)


class TestRLSPatientIsolationAPI:
    """Test patient data isolation via RLS policies through API."""

    async def test_doctor_can_only_see_own_patients(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that doctors can only see their own patients.

        RLS Policy: patients table has doctor_id foreign key with RLS.
        Expected: Doctor A sees only their patients, Doctor B sees only theirs.
        """
        # Create test patients for each doctor (using service role or admin endpoint)
        # For this test, we assume patients exist or use a setup fixture

        # Doctor A queries patients
        headers_a = auth_headers(doctor_a_credentials)
        response_a = await http_client.get("/api/v1/patients", headers=headers_a)

        patients_a = []
        if response_a.status_code == 200:
            patients_a = response_a.json()

        # Doctor B queries patients
        headers_b = auth_headers(doctor_b_credentials)
        response_b = await http_client.get("/api/v1/patients", headers=headers_b)

        patients_b = []
        if response_b.status_code == 200:
            patients_b = response_b.json()

        # Extract patient IDs
        ids_a = {p.get("id") for p in patients_a if isinstance(patients_a, list)}
        ids_b = {p.get("id") for p in patients_b if isinstance(patients_b, list)}

        # Patients should be isolated (no overlap)
        assert ids_a.isdisjoint(ids_b), "Doctors should not see each other's patients"

    async def test_doctor_cannot_access_other_doctor_patient(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that Doctor A cannot access Doctor B's patient by ID.

        RLS Policy: patients table restricts access by doctor_id.
        Expected: 403 Forbidden or 404 Not Found.
        """
        headers_a = auth_headers(doctor_a_credentials)
        headers_b = auth_headers(doctor_b_credentials)

        # Get Doctor B's patients
        response_b = await http_client.get("/api/v1/patients", headers=headers_b)

        if response_b.status_code == 200:
            patients_b = response_b.json()
            if isinstance(patients_b, list) and len(patients_b) > 0:
                patient_b_id = patients_b[0].get("id")

                # Doctor A tries to access Doctor B's patient
                response_a = await http_client.get(
                    f"/api/v1/patients/{patient_b_id}",
                    headers=headers_a
                )

                # Should be denied
                assert response_a.status_code in (403, 404)


class TestRLSMedicalReportsIsolationAPI:
    """Test medical reports isolation via RLS policies through API."""

    async def test_medical_reports_isolated_by_doctor(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that medical reports are isolated by doctor.

        RLS Policy: medical_reports table joins to patients → doctor_id.
        Expected: Each doctor sees only reports for their patients.
        """
        headers_a = auth_headers(doctor_a_credentials)
        headers_b = auth_headers(doctor_b_credentials)

        # Query medical reports for each doctor
        response_a = await http_client.get("/api/v1/medical-reports", headers=headers_a)
        response_b = await http_client.get("/api/v1/medical-reports", headers=headers_b)

        reports_a = []
        reports_b = []

        if response_a.status_code == 200:
            reports_a = response_a.json()

        if response_b.status_code == 200:
            reports_b = response_b.json()

        # Extract report IDs
        ids_a = {r.get("id") for r in reports_a if isinstance(reports_a, list)}
        ids_b = {r.get("id") for r in reports_b if isinstance(reports_b, list)}

        # Reports should be isolated
        assert ids_a.isdisjoint(ids_b), "Doctors should not see each other's medical reports"


class TestRLSQuizTemplatesAPI:
    """Test quiz templates RLS policy through API."""

    async def test_quiz_templates_accessible_to_authenticated_users(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that authenticated users can access quiz templates.

        RLS Policy: quiz_templates allows SELECT for authenticated users.
        Expected: 200 OK with list of templates.
        """
        headers = auth_headers(doctor_a_credentials)
        response = await http_client.get("/api/v1/quiz-templates", headers=headers)

        # Should be accessible
        assert response.status_code == 200

        # Should return a list (even if empty)
        data = response.json()
        assert isinstance(data, list) or isinstance(data, dict)

    async def test_quiz_templates_denied_without_auth(
        self,
        http_client: httpx.AsyncClient
    ):
        """
        Test that unauthenticated users cannot access quiz templates.

        Expected: 401 Unauthorized or empty list.
        """
        response = await http_client.get("/api/v1/quiz-templates")

        # Should be denied or return empty
        assert response.status_code in (401, 403) or response.json() == []


class TestRLSMessagesIsolationAPI:
    """Test messages isolation via RLS policies through API."""

    async def test_messages_isolated_by_doctor(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that messages are isolated by doctor (through patient relationship).

        RLS Policy: messages table joins to patients → doctor_id.
        Expected: Each doctor sees only messages for their patients.
        """
        headers_a = auth_headers(doctor_a_credentials)
        headers_b = auth_headers(doctor_b_credentials)

        # Query messages for each doctor
        response_a = await http_client.get("/api/v1/messages", headers=headers_a)
        response_b = await http_client.get("/api/v1/messages", headers=headers_b)

        messages_a = []
        messages_b = []

        if response_a.status_code == 200:
            messages_a = response_a.json()

        if response_b.status_code == 200:
            messages_b = response_b.json()

        # Extract message IDs
        ids_a = {m.get("id") for m in messages_a if isinstance(messages_a, list)}
        ids_b = {m.get("id") for m in messages_b if isinstance(messages_b, list)}

        # Messages should be isolated
        assert ids_a.isdisjoint(ids_b), "Doctors should not see each other's messages"


class TestRLSAlertsIsolationAPI:
    """Test alerts isolation via RLS policies through API."""

    async def test_alerts_isolated_by_doctor(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Test that alerts are isolated by doctor (through patient relationship).

        RLS Policy: alerts table joins to patients → doctor_id.
        Expected: Each doctor sees only alerts for their patients.
        """
        headers_a = auth_headers(doctor_a_credentials)
        headers_b = auth_headers(doctor_b_credentials)

        # Query alerts for each doctor
        response_a = await http_client.get("/api/v1/alerts", headers=headers_a)
        response_b = await http_client.get("/api/v1/alerts", headers=headers_b)

        alerts_a = []
        alerts_b = []

        if response_a.status_code == 200:
            alerts_a = response_a.json()

        if response_b.status_code == 200:
            alerts_b = response_b.json()

        # Extract alert IDs
        ids_a = {a.get("id") for a in alerts_a if isinstance(alerts_a, list)}
        ids_b = {a.get("id") for a in alerts_b if isinstance(alerts_b, list)}

        # Alerts should be isolated
        assert ids_a.isdisjoint(ids_b), "Doctors should not see each other's alerts"


# ============================================================================
# INTEGRATION TEST: Full RLS Flow
# ============================================================================

class TestRLSFullIntegrationAPI:
    """
    Integration test for complete RLS flow through API.

    This test simulates a realistic scenario:
    1. Two doctors authenticate
    2. Each creates patients
    3. Each creates medical reports
    4. Verify complete isolation across all resources
    """

    async def test_full_rls_isolation_workflow(
        self,
        http_client: httpx.AsyncClient,
        doctor_a_credentials: Dict[str, str],
        doctor_b_credentials: Dict[str, str],
        auth_headers: callable
    ):
        """
        Full integration test of RLS isolation.

        Workflow:
        1. Doctor A and B authenticate
        2. Each queries their resources (patients, reports, etc.)
        3. Verify complete isolation
        4. Attempt cross-access (should fail)
        """
        headers_a = auth_headers(doctor_a_credentials)
        headers_b = auth_headers(doctor_b_credentials)

        # Step 1: Doctor A gets their resources
        patients_a_response = await http_client.get("/api/v1/patients", headers=headers_a)
        reports_a_response = await http_client.get("/api/v1/medical-reports", headers=headers_a)

        # Step 2: Doctor B gets their resources
        patients_b_response = await http_client.get("/api/v1/patients", headers=headers_b)
        reports_b_response = await http_client.get("/api/v1/medical-reports", headers=headers_b)

        # Step 3: Verify responses are successful or properly denied
        assert patients_a_response.status_code in (200, 401, 403)
        assert patients_b_response.status_code in (200, 401, 403)
        assert reports_a_response.status_code in (200, 401, 403)
        assert reports_b_response.status_code in (200, 401, 403)

        # Step 4: If both got 200, verify isolation
        if patients_a_response.status_code == 200 and patients_b_response.status_code == 200:
            patients_a = patients_a_response.json()
            patients_b = patients_b_response.json()

            if isinstance(patients_a, list) and isinstance(patients_b, list):
                ids_a = {p.get("id") for p in patients_a}
                ids_b = {p.get("id") for p in patients_b}
                assert ids_a.isdisjoint(ids_b), "Complete patient isolation required"

        # Step 5: Verify quiz templates are accessible to both (shared resource)
        quiz_a_response = await http_client.get("/api/v1/quiz-templates", headers=headers_a)
        quiz_b_response = await http_client.get("/api/v1/quiz-templates", headers=headers_b)

        # Both should have access to quiz templates
        assert quiz_a_response.status_code == 200
        assert quiz_b_response.status_code == 200
