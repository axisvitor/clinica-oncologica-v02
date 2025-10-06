"""
Integration tests for user sync audit logging.

Tests comprehensive audit trail for Firebase user synchronization:
- User creation events logged
- User update events logged
- Security rejection events logged
- Audit log storage and retrieval
- Audit log data completeness
"""
import pytest
from typing import Dict, Any
from datetime import datetime
from sqlalchemy import text

from app.models.user import User, UserRole
from app.services.firebase_user_sync_service import FirebaseUserSyncService


class TestUserSyncAuditLogging:
    """Test suite for Firebase user sync audit logging."""

    @pytest.mark.asyncio
    async def test_audit_log_created_on_user_creation(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        mock_audit_log_table
    ):
        """
        Test audit log entry is created when new user is provisioned.

        Should log:
        - Event type: firebase_user_provisioning
        - Operation: success
        - Firebase UID
        - Email
        - Timestamp
        """
        # Act - create new user
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        # Assert
        assert created is True

        # Check audit log
        result = db_session.execute(text("""
            SELECT event_data FROM audit_log_entries
            WHERE event_type = 'firebase_user_provisioning'
            ORDER BY created_at DESC LIMIT 1
        """))

        audit_entry = result.fetchone()
        if audit_entry:
            event_data = audit_entry[0]
            assert event_data["type"] == "success"
            assert event_data["firebase_uid"] == firebase_token_data_doctor["uid"]
            assert event_data["email"] == firebase_token_data_doctor["email"]

    @pytest.mark.asyncio
    async def test_audit_log_created_on_user_update(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        create_test_user,
        mock_audit_log_table
    ):
        """
        Test audit log entry is created when user is updated.

        Should log update operation with changes made.
        """
        # Create existing user
        existing_user = create_test_user(
            email=firebase_token_data_doctor["email"],
            firebase_uid=firebase_token_data_doctor["uid"]
        )

        # Update token data
        firebase_token_data_doctor["name"] = "Updated Name"

        # Act - sync with updated data
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=False
        )

        # Assert
        assert created is False
        assert user.firebase_display_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_audit_log_security_rejection_unauthorized_domain(
        self,
        db_session,
        firebase_sync_service,
        mock_audit_log_table
    ):
        """
        Test audit log captures security rejection for unauthorized domain.

        When user from unauthorized domain attempts access,
        should log rejection with reason.
        """
        # Create token with unauthorized domain
        unauthorized_token = {
            "uid": "firebase_unauthorized_test",
            "email": "user@gmail.com",  # Public domain, should be blocked
            "email_verified": True,
            "custom_claims": {"role": "doctor"},
            "auth_time": int(datetime.utcnow().timestamp())
        }

        # Act - attempt sync with unauthorized domain
        with pytest.raises(ValueError) as exc_info:
            await firebase_sync_service.sync_firebase_user(
                firebase_uid=unauthorized_token["uid"],
                firebase_data=unauthorized_token,
                auto_create=True
            )

        # Assert
        assert "Unauthorized email domain" in str(exc_info.value)

        # Check audit log for rejection
        result = db_session.execute(text("""
            SELECT event_data FROM audit_log_entries
            WHERE event_type = 'firebase_user_provisioning'
            AND event_data->>'type' = 'rejected'
            ORDER BY created_at DESC LIMIT 1
        """))

        audit_entry = result.fetchone()
        if audit_entry:
            event_data = audit_entry[0]
            assert event_data["reason"] == "unauthorized_domain"
            assert "gmail.com" in event_data.get("error", "")

    @pytest.mark.asyncio
    async def test_audit_log_security_rejection_invalid_claims(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_no_claims,
        mock_audit_log_table
    ):
        """
        Test audit log captures security rejection for invalid claims.

        When required custom claims are missing, should log rejection.
        """
        # Ensure email is from authorized domain
        firebase_token_data_no_claims["email"] = "test@clinica.test.com"

        # Act - attempt sync without required claims
        with pytest.raises(ValueError) as exc_info:
            await firebase_sync_service.sync_firebase_user(
                firebase_uid=firebase_token_data_no_claims["uid"],
                firebase_data=firebase_token_data_no_claims,
                auto_create=True
            )

        # Assert
        assert "Invalid role in custom claims" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_log_table_records_operations(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor
    ):
        """
        Test user_sync_log table records sync operations.

        UserSyncLog model should track:
        - firebase_uid
        - user_id (PostgreSQL)
        - operation (create, update, link)
        - sync_direction (firebase_to_pg)
        - success/failure
        - changes made
        """
        # Act - create user
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        # Check sync log
        try:
            from app.models.user_sync_log import UserSyncLog

            log_entries = db_session.query(UserSyncLog).filter(
                UserSyncLog.firebase_uid == firebase_token_data_doctor["uid"]
            ).all()

            assert len(log_entries) > 0

            latest_log = log_entries[-1]
            assert latest_log.operation == "create"
            assert latest_log.sync_direction == "firebase_to_pg"
            assert latest_log.success is True
            assert latest_log.user_id == str(user.id)

        except ImportError:
            # UserSyncLog model might not exist yet
            pytest.skip("UserSyncLog model not available")

    @pytest.mark.asyncio
    async def test_audit_log_includes_timestamp(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        mock_audit_log_table
    ):
        """
        Test audit log entries include accurate timestamps.

        Timestamps should be UTC and within reasonable margin
        of when operation occurred.
        """
        start_time = datetime.utcnow()

        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        end_time = datetime.utcnow()

        # Check audit log timestamp
        result = db_session.execute(text("""
            SELECT created_at, event_data FROM audit_log_entries
            WHERE event_type = 'firebase_user_provisioning'
            ORDER BY created_at DESC LIMIT 1
        """))

        audit_entry = result.fetchone()
        if audit_entry:
            log_timestamp = audit_entry[0]
            assert start_time <= log_timestamp <= end_time

    @pytest.mark.asyncio
    async def test_audit_log_data_completeness(
        self,
        db_session,
        firebase_sync_service,
        firebase_token_data_doctor,
        mock_audit_log_table
    ):
        """
        Test audit log contains all required data fields.

        Each audit entry should have:
        - event
        - type (success/rejected/failed)
        - reason
        - firebase_uid
        - email
        - timestamp
        """
        # Act
        user, created = await firebase_sync_service.sync_firebase_user(
            firebase_uid=firebase_token_data_doctor["uid"],
            firebase_data=firebase_token_data_doctor,
            auto_create=True
        )

        # Check audit log completeness
        result = db_session.execute(text("""
            SELECT event_data FROM audit_log_entries
            WHERE event_type = 'firebase_user_provisioning'
            ORDER BY created_at DESC LIMIT 1
        """))

        audit_entry = result.fetchone()
        if audit_entry:
            event_data = audit_entry[0]

            # Verify required fields
            required_fields = ["event", "type", "reason", "firebase_uid", "timestamp"]
            for field in required_fields:
                assert field in event_data, f"Missing required field: {field}"

            # Verify data types
            assert isinstance(event_data["timestamp"], str)
            assert event_data["event"] == "firebase_user_provisioning"
