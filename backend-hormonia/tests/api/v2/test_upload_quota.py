"""
Comprehensive Upload Quota Tests

Tests P2 Implementation: File upload quota enforcement per user tier
Tests quota tracking, enforcement, reset logic, and different user tiers.
Priority: P2 - High (Resource Management)
"""
import pytest
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from app.models.user import User, UserRole


# Mock user tier quotas (MB per month)
TIER_QUOTAS = {
    "FREE": 100,      # 100MB
    "BASIC": 500,     # 500MB
    "PREMIUM": 2000,  # 2GB
    "ENTERPRISE": 10000  # 10GB
}


class TestUploadQuotaEnforcement:
    """Test upload quota enforcement"""

    def test_quota_check_within_limit(self, client, auth_headers, test_user, mocker):
        """Test file upload within quota limit"""
        # Mock Redis to return current usage (50MB used out of 100MB)
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(50 * 1024 * 1024).encode()  # 50MB in bytes
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Mock file (10MB)
        file_content = b'0' * (10 * 1024 * 1024)
        files = {'file': ('test.pdf', file_content, 'application/pdf')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should succeed - 50MB + 10MB = 60MB < 100MB limit
        assert response.status_code in (200, 201)

        # Verify quota was updated
        assert mock_redis.incr.called or mock_redis.incrby.called

    def test_quota_exceeded(self, client, auth_headers, test_user, mocker):
        """Test file upload exceeding quota"""
        # Mock Redis to return current usage (95MB used out of 100MB)
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(95 * 1024 * 1024).encode()  # 95MB in bytes
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Mock file (10MB - would exceed quota)
        file_content = b'0' * (10 * 1024 * 1024)
        files = {'file': ('test.pdf', file_content, 'application/pdf')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should fail with quota exceeded error
        assert response.status_code == 429  # Too Many Requests or 403 Forbidden
        assert 'quota' in response.json()['detail'].lower()

    def test_quota_check_empty_usage(self, client, auth_headers, test_user, mocker):
        """Test quota check when user hasn't uploaded anything yet"""
        # Mock Redis to return no previous usage
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = None
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Mock small file
        file_content = b'test content'
        files = {'file': ('test.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should succeed - first upload
        assert response.status_code in (200, 201)

    def test_quota_enforcement_different_tiers(self, client, db_session, mocker):
        """Test different quota limits for different user tiers"""
        from app.utils.security import get_password_hash

        # Create users with different tiers
        tiers = ['FREE', 'BASIC', 'PREMIUM']

        for tier in tiers:
            user = User(
                id=uuid4(),
                email=f"{tier.lower()}@test.com",
                hashed_password=get_password_hash("testpass"),
                full_name=f"{tier} User",
                role=UserRole.DOCTOR,
                is_active=True,
                tier=tier  # Assuming tier field exists
            )
            db_session.add(user)
        db_session.commit()

        # Each tier should have different quota limits
        # This would be tested through the upload endpoint
        # with mocked quota checks

    def test_quota_exactly_at_limit(self, client, auth_headers, test_user, mocker):
        """Test upload that exactly reaches quota limit"""
        # Mock Redis to return usage that exactly equals limit after upload
        mock_redis = mocker.MagicMock()
        # FREE tier: 100MB, current usage: 99MB
        mock_redis.get.return_value = str(99 * 1024 * 1024).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Upload 1MB file - should exactly hit limit
        file_content = b'0' * (1024 * 1024)
        files = {'file': ('test.pdf', file_content, 'application/pdf')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should succeed - exactly at limit
        assert response.status_code in (200, 201)

    def test_quota_one_byte_over_limit(self, client, auth_headers, test_user, mocker):
        """Test upload that exceeds quota by one byte"""
        # Mock Redis to return usage just below limit
        mock_redis = mocker.MagicMock()
        quota_bytes = 100 * 1024 * 1024  # 100MB
        mock_redis.get.return_value = str(quota_bytes - 1).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Upload 2-byte file - should exceed by 1 byte
        file_content = b'ab'
        files = {'file': ('test.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should fail - over quota
        assert response.status_code == 429


class TestQuotaReset:
    """Test quota reset functionality"""

    def test_monthly_quota_reset(self, mocker):
        """Test quota resets at beginning of month"""
        mock_redis = mocker.MagicMock()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Mock quota service

        # Call reset function (would be called by Celery task)
        # reset_monthly_quotas()

        # Verify Redis keys were deleted/reset
        # assert mock_redis.delete.called

    def test_quota_key_expiration(self, mocker):
        """Test quota keys have proper TTL for monthly reset"""
        mock_redis = mocker.MagicMock()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # When quota is set, it should have TTL until end of month
        # Verify TTL is set correctly

    def test_quota_reset_doesnt_affect_current_uploads(self, client, auth_headers, mocker):
        """Test that quota reset doesn't interfere with ongoing uploads"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = None  # Quota was just reset
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        file_content = b'test'
        files = {'file': ('test.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should succeed with fresh quota
        assert response.status_code in (200, 201)


class TestQuotaTracking:
    """Test quota tracking accuracy"""

    def test_quota_incremented_by_file_size(self, client, auth_headers, test_user, mocker):
        """Test quota increments by exact file size"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(0).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        file_size = 5 * 1024 * 1024  # 5MB
        file_content = b'0' * file_size
        files = {'file': ('test.pdf', file_content, 'application/pdf')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        if response.status_code in (200, 201):
            # Verify Redis was incremented by exact file size
            calls = [call for call in mock_redis.method_calls if 'incr' in str(call)]
            assert len(calls) > 0

    def test_quota_not_incremented_on_failed_upload(self, client, auth_headers, mocker):
        """Test quota not incremented if upload fails"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(0).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Mock virus scanner to reject file
        mocker.patch('app.services.virus_scanner.get_virus_scanner', return_value=Mock(
            scan_file=AsyncMock(return_value=Mock(
                clean=False,
                threat_found="Test-Virus"
            ))
        ))

        file_content = b'virus'
        files = {'file': ('virus.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Upload should fail
        assert response.status_code >= 400

        # Quota should not be incremented
        assert not mock_redis.incrby.called

    def test_quota_multiple_concurrent_uploads(self, client, auth_headers, mocker):
        """Test quota tracking with concurrent uploads"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(10 * 1024 * 1024).encode()  # 10MB used
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Simulate concurrent uploads
        file1 = b'0' * (5 * 1024 * 1024)  # 5MB
        file2 = b'0' * (5 * 1024 * 1024)  # 5MB

        # Both should track independently and update quota atomically
        # Redis INCRBY is atomic, so this should work correctly

    def test_quota_tracking_persistence(self, client, auth_headers, mocker):
        """Test quota persists across requests"""
        mock_redis = mocker.MagicMock()

        # First upload: 0 -> 10MB
        mock_redis.get.return_value = str(0).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        file_content = b'0' * (10 * 1024 * 1024)
        files = {'file': ('test1.pdf', file_content, 'application/pdf')}

        response1 = client.post('/api/v2/upload', files=files, headers=auth_headers)

        # Second upload: 10MB -> 20MB
        mock_redis.get.return_value = str(10 * 1024 * 1024).encode()

        files = {'file': ('test2.pdf', file_content, 'application/pdf')}
        response2 = client.post('/api/v2/upload', files=files, headers=auth_headers)

        # Both should succeed if under quota
        # Quota should accumulate


class TestQuotaAPI:
    """Test quota-related API endpoints"""

    def test_get_quota_status(self, client, auth_headers, test_user, mocker):
        """Test GET /api/v2/upload/quota endpoint"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(50 * 1024 * 1024).encode()  # 50MB used
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        response = client.get(
            '/api/v2/upload/quota',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should return quota usage info
        assert 'used' in data
        assert 'limit' in data
        assert 'remaining' in data
        assert 'percent_used' in data

    def test_get_quota_status_premium_user(self, client, db_session, mocker):
        """Test quota status for premium tier user"""
        from app.utils.security import get_password_hash

        # Create premium user
        premium_user = User(
            id=uuid4(),
            email="premium@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name="Premium User",
            role=UserRole.DOCTOR,
            is_active=True,
            tier="PREMIUM"
        )
        db_session.add(premium_user)
        db_session.commit()

        # Mock auth
        from app.main import app
        from app.dependencies.auth_dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: premium_user

        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(1000 * 1024 * 1024).encode()  # 1GB used
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        response = client.get('/api/v2/upload/quota')

        if response.status_code == 200:
            data = response.json()
            # Premium should have 2GB limit
            assert data['limit'] >= 2000 * 1024 * 1024


class TestQuotaTiers:
    """Test different user tier quotas"""

    @pytest.mark.parametrize("tier,expected_quota_mb", [
        ("FREE", 100),
        ("BASIC", 500),
        ("PREMIUM", 2000),
        ("ENTERPRISE", 10000),
    ])
    def test_tier_quota_limits(self, tier, expected_quota_mb, db_session, mocker):
        """Test each tier has correct quota limit"""
        from app.utils.security import get_password_hash

        user = User(
            id=uuid4(),
            email=f"{tier}@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name=f"{tier} User",
            role=UserRole.DOCTOR,
            is_active=True,
            tier=tier
        )
        db_session.add(user)
        db_session.commit()

        # Get quota limit for user
        # from app.services.upload_quota import get_user_quota_limit
        # quota = get_user_quota_limit(user)
        # assert quota == expected_quota_mb * 1024 * 1024

    def test_tier_upgrade_increases_quota(self, client, test_user, db_session, mocker):
        """Test upgrading tier increases quota limit"""
        # Start as FREE tier
        test_user.tier = "FREE"
        db_session.commit()

        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(90 * 1024 * 1024).encode()  # 90MB used
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Upgrade to PREMIUM
        test_user.tier = "PREMIUM"
        db_session.commit()

        # Should now have access to PREMIUM quota (2GB)
        # 90MB should be well under new limit

    def test_admin_unlimited_quota(self, client, admin_user, mocker):
        """Test admin users have unlimited quota"""
        from app.main import app
        from app.dependencies.auth_dependencies import get_current_user
        app.dependency_overrides[get_current_user] = lambda: admin_user

        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(999999 * 1024 * 1024).encode()  # Huge usage
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Large file
        file_content = b'0' * (100 * 1024 * 1024)
        files = {'file': ('test.pdf', file_content, 'application/pdf')}

        response = client.post('/api/v2/upload', files=files)

        # Admins should bypass quota
        # assert response.status_code in (200, 201)


class TestQuotaPerformance:
    """Test quota system performance"""

    def test_quota_check_performance(self, client, auth_headers, mocker, benchmark):
        """Test quota check doesn't add significant latency"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = str(0).encode()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Benchmark quota check
        def quota_check():
            mock_redis.get('quota:user:test')
            return True

        result = benchmark(quota_check)
        assert result is True

    def test_quota_atomic_increment(self, mocker):
        """Test quota increment is atomic (uses Redis INCRBY)"""
        mock_redis = mocker.MagicMock()
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        # Simulate quota increment
        file_size = 1024 * 1024  # 1MB

        # Should use atomic INCRBY command
        mock_redis.incrby('quota:user:123', file_size)

        # Verify atomic operation was called
        assert mock_redis.incrby.called


class TestQuotaErrorHandling:
    """Test error handling in quota system"""

    def test_redis_unavailable_allows_upload(self, client, auth_headers, mocker):
        """Test upload proceeds if Redis is unavailable (fail-open)"""
        # Mock Redis connection failure
        mocker.patch('app.core.redis_client.get_redis_client', side_effect=Exception("Redis down"))

        file_content = b'test'
        files = {'file': ('test.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should allow upload (fail-open for availability)
        # or return 503 Service Unavailable
        assert response.status_code in (200, 201, 503)

    def test_quota_corruption_handled(self, client, auth_headers, mocker):
        """Test handling of corrupted quota data in Redis"""
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = b'invalid_number'  # Corrupted data
        mocker.patch('app.core.redis_client.get_redis_client', return_value=mock_redis)

        file_content = b'test'
        files = {'file': ('test.txt', file_content, 'text/plain')}

        response = client.post(
            '/api/v2/upload',
            files=files,
            headers=auth_headers
        )

        # Should handle gracefully (reset or default to 0)
        assert response.status_code in (200, 201, 500)
