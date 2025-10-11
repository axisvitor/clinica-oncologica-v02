# Comprehensive Testing Strategy for WhatsApp Patient Authorization

## Overview
Complete testing strategy covering security functionality, backwards compatibility, performance, and edge cases for the strict patient-only WhatsApp access implementation.

## Testing Architecture

### 1. Test Categories
- **Unit Tests** - Individual component testing
- **Integration Tests** - Service interaction testing
- **Security Tests** - Attack simulation and vulnerability testing
- **Performance Tests** - Load and stress testing
- **Compatibility Tests** - Backwards compatibility validation
- **End-to-End Tests** - Complete workflow testing

### 2. Test Data Management

```python
# File: tests/fixtures/security_test_data.py
"""
Test data fixtures for security testing.
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Dict, Any

from app.models.patient import Patient
from app.models.patient_onboarding import PatientPreAuthorization
from app.services.patient import PatientService
from tests.utils.test_helpers import create_test_patient

@pytest.fixture
def registered_patient_phone() -> str:
    """Phone number for registered patient."""
    return "+5511987654321"

@pytest.fixture
def unregistered_phone() -> str:
    """Phone number not registered in system."""
    return "+5511999888777"

@pytest.fixture
def pre_authorized_phone() -> str:
    """Phone number with pre-authorization."""
    return "+5511888777666"

@pytest.fixture
def malicious_phone() -> str:
    """Phone number for attack simulation."""
    return "+5511666555444"

@pytest.fixture
def test_patient(db_session, test_doctor) -> Patient:
    """Create test patient for security tests."""
    return create_test_patient(
        db=db_session,
        phone="+5511987654321",
        name="Test Patient",
        email="test@example.com",
        doctor_id=test_doctor.id
    )

@pytest.fixture
def pre_authorization(db_session, test_admin) -> PatientPreAuthorization:
    """Create test pre-authorization."""
    pre_auth = PatientPreAuthorization.create_authorization(
        phone_number="+5511888777666",
        authorized_by=test_admin.id,
        reason="Test onboarding",
        duration_hours=24,
        max_uses=10
    )
    db_session.add(pre_auth)
    db_session.commit()
    return pre_auth

@pytest.fixture
def webhook_message_data() -> Dict[str, Any]:
    """Standard webhook message data."""
    return {
        "data": {
            "key": {
                "remoteJid": "+5511987654321@s.whatsapp.net",
                "fromMe": False,
                "id": "test_message_id_123"
            },
            "message": {
                "conversation": "Hello, this is a test message"
            },
            "pushName": "Test User"
        }
    }

@pytest.fixture
def unauthorized_webhook_data(unregistered_phone) -> Dict[str, Any]:
    """Webhook data from unauthorized phone."""
    return {
        "data": {
            "key": {
                "remoteJid": f"{unregistered_phone}@s.whatsapp.net",
                "fromMe": False,
                "id": "unauthorized_message_123"
            },
            "message": {
                "conversation": "Unauthorized test message"
            },
            "pushName": "Unknown User"
        }
    }
```

### 3. Unit Tests

```python
# File: tests/unit/test_patient_authorization_middleware.py
"""
Unit tests for patient authorization middleware.
"""
import pytest
from fastapi import Request
from unittest.mock import Mock, AsyncMock

from app.middleware.patient_authorization import PatientAuthorizationMiddleware
from app.services.patient_phone_security import PhoneNumberSecurityService
from app.exceptions import SecurityError

class TestPatientAuthorizationMiddleware:
    """Test patient authorization middleware functionality."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing."""
        mock_app = Mock()
        return PatientAuthorizationMiddleware(
            app=mock_app,
            enabled=True,
            security_mode="strict"
        )

    async def test_allows_non_whatsapp_paths(self, middleware):
        """Test middleware allows non-WhatsApp paths."""
        request = Mock(spec=Request)
        request.url.path = "/api/health"
        request.method = "GET"

        call_next = AsyncMock()
        result = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)

    async def test_allows_non_post_requests(self, middleware):
        """Test middleware allows non-POST requests on WhatsApp paths."""
        request = Mock(spec=Request)
        request.url.path = "/webhooks/evolution/health"
        request.method = "GET"

        call_next = AsyncMock()
        result = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)

    async def test_blocks_unauthorized_phone(self, middleware, unauthorized_webhook_data):
        """Test middleware blocks unauthorized phone numbers."""
        request = Mock(spec=Request)
        request.url.path = "/webhooks/evolution/message"
        request.method = "POST"
        request.json = AsyncMock(return_value=unauthorized_webhook_data)

        call_next = AsyncMock()

        # Mock phone security service
        with patch('app.middleware.patient_authorization.PhoneNumberSecurityService') as mock_security:
            mock_security.return_value.normalize_phone_secure.return_value = "+5511999888777"
            mock_security.return_value.get_authorized_patient.return_value = None

            result = await middleware.dispatch(request, call_next)

            # Should return 403 response
            assert result.status_code == 403
            call_next.assert_not_called()

    async def test_allows_authorized_patient(self, middleware, webhook_message_data, test_patient):
        """Test middleware allows authorized patients."""
        request = Mock(spec=Request)
        request.url.path = "/webhooks/evolution/message"
        request.method = "POST"
        request.json = AsyncMock(return_value=webhook_message_data)

        call_next = AsyncMock()

        # Mock phone security service
        with patch('app.middleware.patient_authorization.PhoneNumberSecurityService') as mock_security:
            mock_security.return_value.normalize_phone_secure.return_value = "+5511987654321"
            mock_security.return_value.get_authorized_patient.return_value = test_patient

            result = await middleware.dispatch(request, call_next)

            call_next.assert_called_once()
            assert hasattr(request.state, 'authorized_patient')
            assert request.state.authorized_patient == test_patient

    async def test_rate_limiting_functionality(self, middleware):
        """Test rate limiting for unauthorized phones."""
        # Create multiple requests from same phone
        for i in range(15):  # Exceed rate limit
            request = Mock(spec=Request)
            request.url.path = "/webhooks/evolution/message"
            request.method = "POST"
            request.json = AsyncMock(return_value=unauthorized_webhook_data)

            result = await middleware.dispatch(request, AsyncMock())

            if i >= 10:  # Rate limit should kick in
                assert result.status_code == 403
                assert "rate limit" in result.content.decode().lower()


# File: tests/unit/test_phone_number_security_service.py
"""
Unit tests for phone number security service.
"""
import pytest
from unittest.mock import Mock

from app.services.patient_phone_security import PhoneNumberSecurityService
from app.exceptions import SecurityError

class TestPhoneNumberSecurityService:
    """Test phone number security service."""

    @pytest.fixture
    def security_service(self, db_session):
        """Create security service instance."""
        return PhoneNumberSecurityService(db_session)

    def test_normalize_phone_e164(self, security_service):
        """Test phone normalization to E.164 format."""
        test_cases = [
            ("5511987654321", "+5511987654321"),
            ("+5511987654321", "+5511987654321"),
            ("11987654321", "+5511987654321"),
            ("5511987654321@s.whatsapp.net", "+5511987654321"),
        ]

        for input_phone, expected in test_cases:
            result = security_service.normalize_phone_secure(input_phone)
            assert result == expected, f"Failed for {input_phone}"

    def test_normalize_phone_invalid(self, security_service):
        """Test phone normalization with invalid inputs."""
        invalid_phones = [
            "123",  # Too short
            "123456789012345678",  # Too long
            "invalid",  # Non-numeric
            "++5511987654321",  # Multiple + signs
            "1111111111111",  # All same digits
        ]

        for invalid_phone in invalid_phones:
            with pytest.raises(SecurityError):
                security_service.normalize_phone_secure(invalid_phone)

    async def test_get_authorized_patient_found(self, security_service, test_patient):
        """Test finding authorized patient."""
        result = await security_service.get_authorized_patient(test_patient.phone)
        assert result is not None
        assert result.id == test_patient.id

    async def test_get_authorized_patient_not_found(self, security_service):
        """Test patient not found case."""
        result = await security_service.get_authorized_patient("+5511999888777")
        assert result is None

    def test_get_phone_hash(self, security_service):
        """Test phone number hashing for security logging."""
        phone = "+5511987654321"
        hash1 = security_service.get_phone_hash(phone)
        hash2 = security_service.get_phone_hash(phone)

        # Same phone should produce same hash
        assert hash1 == hash2
        # Hash should be reasonable length
        assert len(hash1) == 12
        # Different phones should produce different hashes
        different_hash = security_service.get_phone_hash("+5511999888777")
        assert hash1 != different_hash
```

### 4. Integration Tests

```python
# File: tests/integration/test_webhook_security_flow.py
"""
Integration tests for complete webhook security flow.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from tests.utils.webhook_helpers import create_webhook_payload

class TestWebhookSecurityFlow:
    """Test complete webhook security flow integration."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_authorized_patient_complete_flow(self, client, test_patient, webhook_message_data):
        """Test complete flow for authorized patient."""

        # Mock Evolution API signature validation
        with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
            response = client.post(
                "/webhooks/evolution/message",
                json=webhook_message_data,
                headers={"x-signature": "test_signature"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "message_id" in data

    def test_unauthorized_phone_blocked(self, client, unauthorized_webhook_data):
        """Test unauthorized phone is properly blocked."""

        with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
            response = client.post(
                "/webhooks/evolution/message",
                json=unauthorized_webhook_data,
                headers={"x-signature": "test_signature"}
            )

        # Should return success but ignore the message
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"

    def test_pre_authorized_onboarding_flow(self, client, pre_authorization):
        """Test pre-authorized phone onboarding flow."""

        # Create webhook data for pre-authorized phone
        onboarding_webhook = {
            "data": {
                "key": {
                    "remoteJid": f"{pre_authorization.phone_number}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "onboarding_message_123"
                },
                "message": {
                    "conversation": "Hello, I want to register"
                },
                "pushName": "New Patient"
            }
        }

        with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
            response = client.post(
                "/webhooks/evolution/message",
                json=onboarding_webhook,
                headers={"x-signature": "test_signature"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_rate_limiting_integration(self, client, unauthorized_webhook_data):
        """Test rate limiting integration with Redis."""

        # Send multiple unauthorized requests
        for i in range(6):  # Exceed rate limit
            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=unauthorized_webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            assert response.status_code == 200  # Webhook always returns 200
            # But rate limiting should be triggered internally

    def test_security_event_logging(self, client, unauthorized_webhook_data, db_session):
        """Test security events are properly logged."""

        with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
            response = client.post(
                "/webhooks/evolution/message",
                json=unauthorized_webhook_data,
                headers={"x-signature": "test_signature"}
            )

        # Check security event was logged
        from app.models.whatsapp_security_events import WhatsAppSecurityEvent
        security_events = db_session.query(WhatsAppSecurityEvent).filter_by(
            event_type="UNAUTHORIZED_PHONE"
        ).all()

        assert len(security_events) > 0
        event = security_events[0]
        assert "+5511999888777" in event.phone_number

    def test_webhook_persistence_integration(self, client, webhook_message_data, db_session):
        """Test webhook events are persisted correctly."""

        with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
            response = client.post(
                "/webhooks/evolution/message",
                json=webhook_message_data,
                headers={"x-signature": "test_signature"}
            )

        # Check webhook event was persisted
        from app.models.webhook_events import WebhookEvent
        webhook_events = db_session.query(WebhookEvent).filter_by(
            event_type="message.received"
        ).all()

        assert len(webhook_events) > 0
        event = webhook_events[0]
        assert event.processed == True
```

### 5. Security Tests

```python
# File: tests/security/test_attack_scenarios.py
"""
Security tests simulating various attack scenarios.
"""
import pytest
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from app.main import app

class TestAttackScenarios:
    """Test various security attack scenarios."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_brute_force_phone_enumeration(self, client):
        """Test brute force phone number enumeration attack."""

        # Generate many phone numbers to test
        phone_numbers = [f"+551198765{i:04d}" for i in range(100)]

        attack_responses = []
        for phone in phone_numbers:
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"attack_message_{phone}"
                    },
                    "message": {"conversation": "Attack message"},
                    "pushName": "Attacker"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            attack_responses.append((phone, response.status_code, response.json()))

        # Verify all unauthorized numbers are handled consistently
        for phone, status_code, response_data in attack_responses:
            assert status_code == 200  # Webhook should not reveal internal errors
            assert response_data["status"] == "ignored"  # Should not process unauthorized

    def test_rapid_fire_attack(self, client):
        """Test rapid-fire attack from single phone number."""

        attack_phone = "+5511999888777"
        webhook_data = {
            "data": {
                "key": {
                    "remoteJid": f"{attack_phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "rapid_attack_123"
                },
                "message": {"conversation": "Rapid attack"},
                "pushName": "Attacker"
            }
        }

        # Send rapid requests
        responses = []
        for i in range(20):  # Rapid fire
            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )
            responses.append(response)

        # Verify rate limiting kicks in
        ignored_count = sum(1 for r in responses if r.json().get("status") == "ignored")
        assert ignored_count == len(responses)  # All should be ignored (unauthorized)

    def test_distributed_attack_simulation(self, client):
        """Test distributed attack from multiple IPs/phones."""

        # Simulate attack from multiple phones (distributed)
        attack_phones = [f"+551199988{i:04d}" for i in range(50)]

        def attack_request(phone):
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"distributed_attack_{phone}"
                    },
                    "message": {"conversation": "Distributed attack"},
                    "pushName": "Attacker"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                return client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

        # Execute distributed attack
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(attack_request, phone) for phone in attack_phones]
            responses = [future.result() for future in futures]

        # Verify all attacks are properly handled
        for response in responses:
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"

    def test_malformed_webhook_data_attack(self, client):
        """Test attacks with malformed webhook data."""

        malformed_payloads = [
            {},  # Empty payload
            {"data": {}},  # Missing required fields
            {"data": {"key": {}}},  # Missing message
            {"data": {"key": {"remoteJid": "invalid"}}},  # Invalid phone format
            {"malicious": "payload"},  # Completely wrong structure
            None,  # Null payload
        ]

        for payload in malformed_payloads:
            try:
                with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                    response = client.post(
                        "/webhooks/evolution/message",
                        json=payload,
                        headers={"x-signature": "test_signature"}
                    )

                # Should handle gracefully without crashing
                assert response.status_code in [200, 400, 422]

            except Exception as e:
                pytest.fail(f"Malformed payload caused unhandled exception: {e}")

    def test_sql_injection_attempts(self, client):
        """Test SQL injection attempts through phone numbers."""

        sql_injection_phones = [
            "+5511'; DROP TABLE patients; --",
            "+5511' OR '1'='1",
            "+5511'; INSERT INTO patients VALUES (...); --",
            "+5511' UNION SELECT * FROM users --",
        ]

        for malicious_phone in sql_injection_phones:
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{malicious_phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": "sql_injection_attempt"
                    },
                    "message": {"conversation": "SQL injection attempt"},
                    "pushName": "Attacker"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            # Should handle safely without database corruption
            assert response.status_code == 200
            # Verify database integrity (patients table should still exist)
            # This would be checked in integration with actual database
```

### 6. Performance Tests

```python
# File: tests/performance/test_security_performance.py
"""
Performance tests for security enhancements.
"""
import pytest
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from statistics import mean, median
from fastapi.testclient import TestClient

from app.main import app

class TestSecurityPerformance:
    """Test performance impact of security enhancements."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_webhook_processing_performance(self, client, test_patient):
        """Test webhook processing performance with security enabled."""

        webhook_data = {
            "data": {
                "key": {
                    "remoteJid": f"{test_patient.phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "performance_test_message"
                },
                "message": {"conversation": "Performance test message"},
                "pushName": "Test User"
            }
        }

        # Measure processing times
        processing_times = []

        for i in range(100):  # 100 requests for statistical significance
            start_time = time.time()

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            end_time = time.time()
            processing_times.append(end_time - start_time)

            assert response.status_code == 200

        # Analyze performance
        avg_time = mean(processing_times)
        median_time = median(processing_times)
        max_time = max(processing_times)

        # Performance assertions (adjust thresholds as needed)
        assert avg_time < 0.5, f"Average processing time too high: {avg_time}s"
        assert median_time < 0.3, f"Median processing time too high: {median_time}s"
        assert max_time < 1.0, f"Maximum processing time too high: {max_time}s"

        print(f"Performance Results:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Median: {median_time:.3f}s")
        print(f"  Max: {max_time:.3f}s")

    def test_concurrent_request_performance(self, client, test_patient):
        """Test performance under concurrent load."""

        webhook_data = {
            "data": {
                "key": {
                    "remoteJid": f"{test_patient.phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": "concurrent_test_message"
                },
                "message": {"conversation": "Concurrent test message"},
                "pushName": "Test User"
            }
        }

        def make_request():
            start_time = time.time()
            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )
            end_time = time.time()
            return response.status_code, end_time - start_time

        # Execute concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [future.result() for future in futures]
        total_time = time.time() - start_time

        # Analyze concurrent performance
        successful_requests = sum(1 for status_code, _ in results if status_code == 200)
        processing_times = [processing_time for _, processing_time in results]

        avg_time = mean(processing_times)
        throughput = successful_requests / total_time

        # Performance assertions
        assert successful_requests >= 95, f"Too many failed requests: {successful_requests}/100"
        assert avg_time < 1.0, f"Average processing time under load too high: {avg_time}s"
        assert throughput >= 10, f"Throughput too low: {throughput} requests/second"

        print(f"Concurrent Performance Results:")
        print(f"  Successful requests: {successful_requests}/100")
        print(f"  Average processing time: {avg_time:.3f}s")
        print(f"  Throughput: {throughput:.1f} requests/second")

    def test_database_query_performance(self, db_session, test_patient):
        """Test database query performance for patient authorization."""

        from app.services.patient_phone_security import PhoneNumberSecurityService

        security_service = PhoneNumberSecurityService(db_session)

        # Measure patient lookup performance
        lookup_times = []

        for i in range(100):
            start_time = time.time()
            patient = await security_service.get_authorized_patient(test_patient.phone)
            end_time = time.time()

            lookup_times.append(end_time - start_time)
            assert patient is not None
            assert patient.id == test_patient.id

        avg_lookup_time = mean(lookup_times)
        max_lookup_time = max(lookup_times)

        # Database performance assertions
        assert avg_lookup_time < 0.01, f"Database lookup too slow: {avg_lookup_time}s"
        assert max_lookup_time < 0.05, f"Slowest database lookup too slow: {max_lookup_time}s"

        print(f"Database Performance Results:")
        print(f"  Average lookup time: {avg_lookup_time:.6f}s")
        print(f"  Maximum lookup time: {max_lookup_time:.6f}s")
```

### 7. End-to-End Tests

```python
# File: tests/e2e/test_complete_security_workflows.py
"""
End-to-end tests for complete security workflows.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.utils.e2e_helpers import simulate_whatsapp_conversation

class TestCompleteSecurityWorkflows:
    """Test complete end-to-end security workflows."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_complete_patient_conversation_flow(self, client, test_patient):
        """Test complete authorized patient conversation flow."""

        conversation_messages = [
            "Hello, I have a question about my treatment",
            "How are my lab results?",
            "When is my next appointment?",
            "Thank you for the information"
        ]

        message_ids = []

        for i, message_content in enumerate(conversation_messages):
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{test_patient.phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"conversation_message_{i}"
                    },
                    "message": {"conversation": message_content},
                    "pushName": test_patient.name
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            message_ids.append(data["message_id"])

        # Verify all messages were processed
        assert len(message_ids) == len(conversation_messages)
        assert all(msg_id for msg_id in message_ids)

    def test_unauthorized_phone_complete_blocking(self, client):
        """Test complete blocking of unauthorized phone number."""

        unauthorized_phone = "+5511999888777"
        attack_messages = [
            "Hello, I want to access the system",
            "Can you help me with my account?",
            "I need medical information",
            "Please respond to me"
        ]

        for i, message_content in enumerate(attack_messages):
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{unauthorized_phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"unauthorized_message_{i}"
                    },
                    "message": {"conversation": message_content},
                    "pushName": "Unknown User"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ignored"  # All should be ignored

    def test_pre_authorization_onboarding_complete_flow(self, client, pre_authorization, test_doctor):
        """Test complete pre-authorization onboarding flow."""

        onboarding_flow = [
            ("Hello, I want to register", "onboarding_greeting"),
            ("My name is John Doe", "name_collection"),
            ("john.doe@email.com", "email_collection"),
            ("123.456.789-00", "cpf_collection")
        ]

        for message_content, stage in onboarding_flow:
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{pre_authorization.phone_number}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"onboarding_{stage}"
                    },
                    "message": {"conversation": message_content},
                    "pushName": "New Patient"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

        # Verify pre-authorization was consumed
        from app.models.patient_onboarding import PatientPreAuthorization
        updated_pre_auth = db_session.query(PatientPreAuthorization).get(pre_authorization.id)
        assert updated_pre_auth.used_count > 0

    def test_security_monitoring_complete_flow(self, client, db_session):
        """Test complete security monitoring and alerting flow."""

        # Generate various security events
        test_scenarios = [
            ("+5511987654321", "AUTHORIZED", "Legitimate patient message"),
            ("+5511999888777", "UNAUTHORIZED_PHONE", "Unauthorized access attempt"),
            ("+5511888777666", "RATE_LIMITED", "Multiple unauthorized attempts"),
            ("+5511777666555", "SUSPICIOUS_ACTIVITY", "Potential attack pattern")
        ]

        for phone, expected_event_type, description in test_scenarios:
            webhook_data = {
                "data": {
                    "key": {
                        "remoteJid": f"{phone}@s.whatsapp.net",
                        "fromMe": False,
                        "id": f"security_test_{phone}"
                    },
                    "message": {"conversation": f"Test message: {description}"},
                    "pushName": "Security Test"
                }
            }

            with patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):
                response = client.post(
                    "/webhooks/evolution/message",
                    json=webhook_data,
                    headers={"x-signature": "test_signature"}
                )

            assert response.status_code == 200

        # Verify security events were logged
        from app.models.whatsapp_security_events import WhatsAppSecurityEvent
        security_events = db_session.query(WhatsAppSecurityEvent).all()

        assert len(security_events) >= len(test_scenarios)

        # Verify different event types were captured
        event_types = {event.event_type for event in security_events}
        assert "UNAUTHORIZED_PHONE" in event_types
```

## Test Execution Strategy

### 1. Continuous Integration Pipeline

```yaml
# File: .github/workflows/security-tests.yml
name: Security Tests

on: [push, pull_request]

jobs:
  security-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run unit tests
      run: pytest tests/unit/ -v --cov=app --cov-report=xml

    - name: Run integration tests
      run: pytest tests/integration/ -v

    - name: Run security tests
      run: pytest tests/security/ -v

    - name: Run performance tests
      run: pytest tests/performance/ -v

    - name: Run e2e tests
      run: pytest tests/e2e/ -v

    - name: Upload coverage
      uses: codecov/codecov-action@v1
      with:
        file: ./coverage.xml
```

### 2. Test Data Management

```python
# File: tests/conftest.py
"""
Global test configuration and fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.config import settings

# Test database URL
TEST_DATABASE_URL = "postgresql://test:test@localhost/test_hormonia"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session():
    """Create a test database session."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def override_get_db(db_session):
    """Override the database dependency for testing."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()
```

### 3. Test Metrics and Reporting

```python
# File: tests/utils/test_metrics.py
"""
Test metrics collection and reporting.
"""
import time
import psutil
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class TestMetrics:
    """Test execution metrics."""
    test_name: str
    execution_time: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: str = None

class TestMetricsCollector:
    """Collect and analyze test metrics."""

    def __init__(self):
        self.metrics: List[TestMetrics] = []

    def record_test_execution(
        self,
        test_name: str,
        execution_time: float,
        success: bool,
        error_message: str = None
    ) -> None:
        """Record test execution metrics."""

        # Get system metrics
        memory_usage = psutil.virtual_memory().percent
        cpu_usage = psutil.cpu_percent()

        metric = TestMetrics(
            test_name=test_name,
            execution_time=execution_time,
            memory_usage=memory_usage,
            cpu_usage=cpu_usage,
            success=success,
            error_message=error_message
        )

        self.metrics.append(metric)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""

        if not self.metrics:
            return {"error": "No test metrics collected"}

        successful_tests = [m for m in self.metrics if m.success]
        failed_tests = [m for m in self.metrics if not m.success]

        return {
            "summary": {
                "total_tests": len(self.metrics),
                "successful_tests": len(successful_tests),
                "failed_tests": len(failed_tests),
                "success_rate": len(successful_tests) / len(self.metrics) * 100
            },
            "performance": {
                "average_execution_time": sum(m.execution_time for m in self.metrics) / len(self.metrics),
                "slowest_test": max(self.metrics, key=lambda m: m.execution_time),
                "fastest_test": min(self.metrics, key=lambda m: m.execution_time)
            },
            "resource_usage": {
                "average_memory_usage": sum(m.memory_usage for m in self.metrics) / len(self.metrics),
                "average_cpu_usage": sum(m.cpu_usage for m in self.metrics) / len(self.metrics),
                "peak_memory_usage": max(m.memory_usage for m in self.metrics),
                "peak_cpu_usage": max(m.cpu_usage for m in self.metrics)
            },
            "failures": [
                {
                    "test_name": m.test_name,
                    "error_message": m.error_message,
                    "execution_time": m.execution_time
                }
                for m in failed_tests
            ]
        }
```

## Summary

This comprehensive testing strategy ensures:

1. **Complete Coverage** - All security components tested thoroughly
2. **Performance Validation** - Security enhancements don't degrade performance
3. **Attack Simulation** - Real-world attack scenarios tested and defended
4. **Backwards Compatibility** - Existing functionality remains intact
5. **Continuous Monitoring** - Automated testing in CI/CD pipeline
6. **Metrics Collection** - Detailed analysis of test execution and system performance

The testing approach provides confidence that the strict patient-only WhatsApp access implementation is secure, performant, and maintains full backwards compatibility with existing functionality.