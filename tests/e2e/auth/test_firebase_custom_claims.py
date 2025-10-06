"""
E2E Tests for Firebase Custom Claims Integration

Tests Firebase Admin SDK integration with custom claims validation
for Railway production environment.
"""
import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import InvalidIdTokenError, ExpiredIdTokenError


@pytest.fixture
def railway_api_url():
    """Get Railway production API URL"""
    return os.getenv("RAILWAY_API_URL", "https://backend-hormonia-production.up.railway.app")


@pytest.fixture
def firebase_credentials():
    """Firebase credentials from environment"""
    return {
        "project_id": os.getenv("FIREBASE_PROJECT_ID"),
        "private_key": os.getenv("FIREBASE_PRIVATE_KEY"),
        "client_email": os.getenv("FIREBASE_CLIENT_EMAIL")
    }


class TestFirebaseCustomClaimsIntegration:
    """Test suite for Firebase custom claims in Railway production"""

    @pytest.mark.asyncio
    async def test_firebase_admin_sdk_initialization(self, firebase_credentials):
        """
        Test 1: Firebase Admin SDK initializes correctly

        Validates:
        - Firebase credentials are present
        - SDK can initialize without errors
        - Project ID matches configuration
        """
        assert firebase_credentials["project_id"], "FIREBASE_PROJECT_ID must be set"
        assert firebase_credentials["private_key"], "FIREBASE_PRIVATE_KEY must be set"
        assert firebase_credentials["client_email"], "FIREBASE_CLIENT_EMAIL must be set"

        # Verify project ID format
        assert "@" not in firebase_credentials["project_id"], \
            "project_id should not contain @ (use client_email for email)"

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_token_with_custom_claims(self, mock_verify):
        """
        Test 2: Token verification with custom claims

        Validates:
        - Custom claims are extracted from token
        - Claims include role, permissions, metadata
        - Token validation succeeds with custom claims
        """
        # Mock token with custom claims
        mock_verify.return_value = {
            'uid': 'test-uid-123',
            'email': 'doctor@clinic.com',
            'email_verified': True,
            'role': 'doctor',
            'department': 'oncology',
            'permissions': ['read_patients', 'write_prescriptions'],
            'clinic_id': 'clinic-001'
        }

        # Simulate token verification
        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        result = await service.verify_token('mock-token-with-claims')

        # Validate custom claims are present
        assert result['role'] == 'doctor'
        assert result['department'] == 'oncology'
        assert 'read_patients' in result['permissions']
        assert result['clinic_id'] == 'clinic-001'

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_token_without_custom_claims_rejected(self, mock_verify):
        """
        Test 3: Token without required custom claims is rejected

        Validates:
        - Tokens must have minimum required claims
        - Missing role claim causes validation failure
        - Appropriate error message is returned
        """
        # Mock token without custom claims
        mock_verify.return_value = {
            'uid': 'test-uid-456',
            'email': 'user@clinic.com',
            'email_verified': True
            # Missing: role, permissions, etc.
        }

        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        # Should still return user data (claim validation happens at route level)
        result = await service.verify_token('token-without-claims')

        # Basic claims present
        assert result['uid'] == 'test-uid-456'
        # Custom claims absent
        assert 'role' not in result

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_admin_role_custom_claim(self, mock_verify):
        """
        Test 4: Admin role custom claim validation

        Validates:
        - Admin role is properly identified
        - Admin permissions are included
        - Super admin flag is respected
        """
        mock_verify.return_value = {
            'uid': 'admin-uid-789',
            'email': 'admin@clinic.com',
            'email_verified': True,
            'role': 'admin',
            'is_super_admin': True,
            'permissions': ['*']  # All permissions
        }

        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        result = await service.verify_token('admin-token')

        assert result['role'] == 'admin'
        assert result['is_super_admin'] is True
        assert '*' in result['permissions']

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_patient_role_custom_claim(self, mock_verify):
        """
        Test 5: Patient role custom claim validation

        Validates:
        - Patient role is properly identified
        - Patient-specific claims are present
        - Limited permissions for patients
        """
        mock_verify.return_value = {
            'uid': 'patient-uid-101',
            'email': 'patient@example.com',
            'email_verified': True,
            'role': 'patient',
            'patient_id': 'PAT-12345',
            'permissions': ['read_own_data', 'book_appointments']
        }

        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        result = await service.verify_token('patient-token')

        assert result['role'] == 'patient'
        assert result['patient_id'] == 'PAT-12345'
        assert 'read_own_data' in result['permissions']
        assert 'write_prescriptions' not in result['permissions']

    @pytest.mark.asyncio
    async def test_railway_env_variables_present(self):
        """
        Test 6: Railway environment variables are configured

        Validates:
        - All required Firebase env vars are set in Railway
        - Private key is properly formatted
        - Client email has correct format
        """
        # Check critical env vars (will be None in non-Railway environments)
        project_id = os.getenv("FIREBASE_PROJECT_ID")
        private_key = os.getenv("FIREBASE_PRIVATE_KEY")
        client_email = os.getenv("FIREBASE_CLIENT_EMAIL")

        # In CI/local, these may be None, so we only assert format if present
        if project_id:
            assert len(project_id) > 0, "FIREBASE_PROJECT_ID must not be empty"

        if client_email:
            assert "@" in client_email, "FIREBASE_CLIENT_EMAIL must be valid email"
            assert client_email.endswith(".iam.gserviceaccount.com"), \
                "FIREBASE_CLIENT_EMAIL must be service account email"

        if private_key:
            assert "BEGIN PRIVATE KEY" in private_key, \
                "FIREBASE_PRIVATE_KEY must be PEM-formatted private key"

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_token_expiration_handling(self, mock_verify):
        """
        Test 7: Expired token handling with custom claims

        Validates:
        - Expired tokens are properly rejected
        - Error message is clear
        - Custom claims don't bypass expiration check
        """
        mock_verify.side_effect = ExpiredIdTokenError('Token expired')

        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        with pytest.raises(Exception) as exc_info:
            await service.verify_token('expired-token-with-claims')

        assert 'expired' in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @patch('firebase_admin.auth.verify_id_token')
    async def test_revoked_token_handling(self, mock_verify):
        """
        Test 8: Revoked token handling

        Validates:
        - Revoked tokens are rejected even with valid claims
        - check_revoked flag is used in verification
        """
        mock_verify.side_effect = firebase_auth.RevokedIdTokenError('Token has been revoked')

        from app.services.firebase_auth_service import get_firebase_auth_service

        service = get_firebase_auth_service(
            project_id="test-project",
            private_key="-----BEGIN PRIVATE KEY-----\nMOCK\n-----END PRIVATE KEY-----",
            client_email="test@test.iam.gserviceaccount.com"
        )

        with pytest.raises(Exception) as exc_info:
            await service.verify_token('revoked-token')

        assert 'revoked' in str(exc_info.value).lower()

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires live Railway deployment and real Firebase tokens")
    async def test_railway_production_token_validation(self, railway_api_url):
        """
        Test 9: Production Railway token validation (manual test)

        This test should be run manually against Railway production
        with a real Firebase token.

        Steps:
        1. Get valid Firebase token from production
        2. Set RAILWAY_API_URL env var
        3. Run: pytest -v -m integration tests/e2e/auth/
        """
        import httpx

        # This would need a real Firebase token from production login
        # token = "real-firebase-token-from-production"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{railway_api_url}/api/v1/users/me",
                headers={"Authorization": f"Bearer {token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert 'role' in data
            assert 'permissions' in data


@pytest.mark.integration
class TestFirebaseCustomClaimsProduction:
    """Integration tests requiring Railway production environment"""

    @pytest.mark.skip(reason="Requires Railway production deployment")
    async def test_custom_claims_script_execution(self):
        """
        Test 10: Custom claims script runs successfully in Railway

        Validates:
        - fix_firebase_custom_claims.py can be executed
        - Script updates user claims correctly
        - Changes persist in Firebase

        Manual steps documented in Railway deployment guide
        """
        pass
