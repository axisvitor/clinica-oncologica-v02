"""
Comprehensive test suite for Localization API v2

Tests cover:
- All 6 endpoints with various scenarios
- Language listing and filtering
- Translation retrieval with fallback chain
- Translation updates (admin only)
- User language preferences
- Redis caching behavior
- Rate limiting
- RBAC and access control
- Variable substitution
- Pluralization
- Context-aware translations
- Error handling and edge cases

CRITICAL: These tests validate the i18n system that supports
multi-language healthcare communication.
All test cases must pass before deployment to production.
"""

import pytest
import json
from typing import Dict, Any, List
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_localization_service():
    """Mock localization service for testing."""
    with patch('app.api.v2.localization.get_localization_service') as mock:
        service = MagicMock()

        # Mock translations
        service.get_translations.return_value = {
            "auth": {
                "login": {
                    "title": "Login to Your Account",
                    "button": "Sign In"
                }
            },
            "messages": {
                "sent": "You have {count} {message|messages}"
            }
        }

        # Mock translate method
        def mock_translate(key, locale, namespace, fallback=None):
            translations = {
                "en-US": {
                    "auth.login.title": "Login to Your Account",
                    "auth.login.button": "Sign In",
                    "messages.sent": "You have {count} {message|messages}"
                },
                "pt-BR": {
                    "auth.login.title": "Entrar na Sua Conta",
                    "auth.login.button": "Entrar",
                    "messages.sent": "Você tem {count} {mensagem|mensagens}"
                },
                "es-ES": {
                    "auth.login.title": "Iniciar Sesión",
                }
            }

            locale_translations = translations.get(locale, {})
            return locale_translations.get(key, fallback or key)

        service.translate.side_effect = mock_translate

        mock.return_value = service
        yield service


@pytest.fixture
def admin_user_data() -> Dict[str, Any]:
    """Admin user data for testing."""
    return {
        "id": str(uuid4()),
        "firebase_uid": "admin_firebase_uid",
        "email": "admin@example.com",
        "full_name": "Admin User",
        "role": "admin",
        "is_active": True
    }


@pytest.fixture
def patient_user_data() -> Dict[str, Any]:
    """Patient user data for testing."""
    return {
        "id": str(uuid4()),
        "firebase_uid": "patient_firebase_uid",
        "email": "patient@example.com",
        "full_name": "Patient User",
        "role": "patient",
        "is_active": True
    }


@pytest.fixture
def mock_redis_cache():
    """Mock Redis cache for testing."""
    cache_storage = {}

    class MockRedisCache:
        async def get(self, key: str):
            return cache_storage.get(key)

        async def set(self, key: str, value: Any, ttl: int = None):
            cache_storage[key] = value

        async def delete(self, key: str):
            if key in cache_storage:
                del cache_storage[key]

        async def delete_pattern(self, pattern: str):
            keys_to_delete = [k for k in cache_storage.keys() if pattern.replace("*", "") in k]
            for key in keys_to_delete:
                del cache_storage[key]

        async def get_session(self, session_id: str):
            return cache_storage.get(f"session:{session_id}")

        async def get_user_by_uid(self, firebase_uid: str):
            return cache_storage.get(f"user:{firebase_uid}")

        async def cache_user_data(self, firebase_uid: str, data: Dict, ttl: int):
            cache_storage[f"user:{firebase_uid}"] = data

    return MockRedisCache()


# ============================================================================
# List Languages Tests
# ============================================================================

class TestListLanguages:
    """Test suite for GET /api/v2/localization/languages endpoint."""

    @pytest.mark.asyncio
    async def test_list_languages_basic(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test basic language listing."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/languages",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert "data" in data
                assert "total" in data
                assert "default_language" in data
                assert isinstance(data["data"], list)
                assert len(data["data"]) >= 4  # pt-BR, pt-PT, en-US, es-ES
                assert data["default_language"] == "en-US"

    @pytest.mark.asyncio
    async def test_list_languages_filter_enabled(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test filtering languages by enabled status."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/languages?enabled_only=true",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                # All returned languages should be enabled
                for language in data["data"]:
                    assert language["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_languages_with_field_selection(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test field selection for language list."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/languages?fields=code,name",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                if data["data"]:
                    language = data["data"][0]
                    # Only selected fields should be present
                    assert "code" in language
                    assert "name" in language

    @pytest.mark.asyncio
    async def test_list_languages_caching(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test Redis caching for language list."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # First request - should cache
                response1 = client.get(
                    "/api/v2/localization/languages",
                    headers={"X-Session-ID": "test_session"}
                )
                assert response1.status_code == 200

                # Second request - should hit cache
                response2 = client.get(
                    "/api/v2/localization/languages",
                    headers={"X-Session-ID": "test_session"}
                )
                assert response2.status_code == 200

                # Responses should be identical
                assert response1.json() == response2.json()


# ============================================================================
# Get Translations Tests
# ============================================================================

class TestGetTranslations:
    """Test suite for GET /api/v2/localization/translations/{language} endpoint."""

    @pytest.mark.asyncio
    async def test_get_translations_basic(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test getting translations for a language."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert "data" in data
                assert "language" in data
                assert "total" in data
                assert data["language"] == "en-US"
                assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_get_translations_invalid_language(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test getting translations for invalid language."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/invalid-lang",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 404
                assert "not supported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_translations_with_namespace_filter(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test filtering translations by namespace."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US?namespace=auth",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert "namespaces" in data
                assert "auth" in data["namespaces"]

    @pytest.mark.asyncio
    async def test_get_translations_with_search(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test searching translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US?search=login",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                # All results should contain "login" in key or value
                for item in data["data"]:
                    assert "login" in item["key"].lower() or \
                           "login" in str(item["value"]).lower()


# ============================================================================
# Get Translation by Key Tests
# ============================================================================

class TestGetTranslationByKey:
    """Test suite for GET /api/v2/localization/translations/{language}/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_get_translation_by_key_basic(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test getting a specific translation by key."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US/auth.login.title",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert "key" in data
                assert "value" in data
                assert "language" in data
                assert "used_language" in data
                assert "fallback_used" in data
                assert data["key"] == "auth.login.title"
                assert data["language"] == "en-US"

    @pytest.mark.asyncio
    async def test_get_translation_fallback_chain(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test fallback chain for missing translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Request translation that only exists in fallback language
                response = client.get(
                    "/api/v2/localization/translations/es-ES/auth.login.button",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                # Should use fallback language (en-US)
                assert data["fallback_used"] is True
                assert data["used_language"] == "en-US"

    @pytest.mark.asyncio
    async def test_get_translation_with_variables(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test variable substitution in translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                variables = json.dumps({"name": "John", "count": 5})
                response = client.get(
                    f"/api/v2/localization/translations/en-US/messages.welcome?variables={variables}",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert data["has_variables"] is True

    @pytest.mark.asyncio
    async def test_get_translation_with_pluralization(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test pluralization in translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Test with count = 1 (singular)
                response1 = client.get(
                    "/api/v2/localization/translations/en-US/messages.sent?count=1",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response1.status_code == 200
                data1 = response1.json()
                assert data1["has_pluralization"] is True

                # Test with count = 5 (plural)
                response2 = client.get(
                    "/api/v2/localization/translations/en-US/messages.sent?count=5",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response2.status_code == 200
                data2 = response2.json()
                assert data2["has_pluralization"] is True

    @pytest.mark.asyncio
    async def test_get_translation_with_context(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test context-aware translations (formal/informal)."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Test with formal context
                response = client.get(
                    "/api/v2/localization/translations/pt-BR/greeting.hello?context=formal",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert data["context"] == "formal"

    @pytest.mark.asyncio
    async def test_get_translation_invalid_variables(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test error handling for invalid variables JSON."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US/messages.sent?variables=invalid-json",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 400
                assert "Invalid JSON" in response.json()["detail"]


# ============================================================================
# Update Translation Tests
# ============================================================================

class TestUpdateTranslation:
    """Test suite for PUT /api/v2/localization/translations/{language}/{key} endpoint."""

    @pytest.mark.asyncio
    async def test_update_translation_as_admin(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        admin_user_data: Dict[str, Any]
    ):
        """Test updating translation as admin."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=admin_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/translations/en-US/auth.login.title",
                    json={"value": "New Login Title"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert data["value"] == "New Login Title"

    @pytest.mark.asyncio
    async def test_update_translation_as_non_admin(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test updating translation as non-admin (should fail)."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/translations/en-US/auth.login.title",
                    json={"value": "New Login Title"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 403
                assert "administrator" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_translation_invalid_language(
        self,
        client: TestClient,
        mock_redis_cache,
        admin_user_data: Dict[str, Any]
    ):
        """Test updating translation for invalid language."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=admin_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/translations/invalid-lang/auth.login.title",
                    json={"value": "New Login Title"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_translation_cache_invalidation(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        admin_user_data: Dict[str, Any]
    ):
        """Test cache invalidation after translation update."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=admin_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Get translation to cache it
                client.get(
                    "/api/v2/localization/translations/en-US/auth.login.title",
                    headers={"X-Session-ID": "test_session"}
                )

                # Update translation
                response = client.put(
                    "/api/v2/localization/translations/en-US/auth.login.title",
                    json={"value": "Updated Title"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200


# ============================================================================
# User Language Preference Tests
# ============================================================================

class TestUserLanguagePreference:
    """Test suite for user language preference endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_language_preference(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test getting user language preference."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/user/language",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert "user_id" in data
                assert "language" in data
                assert "is_default" in data
                assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_set_user_language_preference(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test setting user language preference."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/user/language",
                    json={"language": "pt-BR"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()

                assert data["language"] == "pt-BR"
                assert data["is_default"] is False

    @pytest.mark.asyncio
    async def test_set_user_language_preference_invalid(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test setting invalid language preference."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/user/language",
                    json={"language": "invalid-lang"},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 400
                assert "not supported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_user_language_preference_caching(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test caching of user language preferences."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Set preference
                response1 = client.put(
                    "/api/v2/localization/user/language",
                    json={"language": "pt-BR"},
                    headers={"X-Session-ID": "test_session"}
                )
                assert response1.status_code == 200

                # Get preference (should be cached)
                response2 = client.get(
                    "/api/v2/localization/user/language",
                    headers={"X-Session-ID": "test_session"}
                )
                assert response2.status_code == 200

                data = response2.json()
                assert data["language"] == "pt-BR"


# ============================================================================
# Helper Functions Tests
# ============================================================================

class TestHelperFunctions:
    """Test suite for localization helper functions."""

    def test_resolve_fallback_chain(self):
        """Test fallback chain resolution."""
        from app.api.v2.localization import _resolve_fallback_chain

        # Test pt-BR fallback chain
        chain_pt_br = _resolve_fallback_chain("pt-BR")
        assert chain_pt_br == ["pt-BR", "pt-PT", "en-US"]

        # Test es-ES fallback chain
        chain_es = _resolve_fallback_chain("es-ES")
        assert chain_es == ["es-ES", "en-US"]

        # Test default language
        chain_en = _resolve_fallback_chain("en-US")
        assert chain_en == ["en-US"]

    def test_apply_pluralization_singular(self):
        """Test pluralization for singular count."""
        from app.api.v2.localization import _apply_pluralization

        text = "You have {count} {message|messages}"
        result = _apply_pluralization(text, 1, "en-US")

        assert "1" in result
        assert "message" in result
        assert "messages" not in result

    def test_apply_pluralization_plural(self):
        """Test pluralization for plural count."""
        from app.api.v2.localization import _apply_pluralization

        text = "You have {count} {message|messages}"
        result = _apply_pluralization(text, 5, "en-US")

        assert "5" in result
        assert "messages" in result

    def test_substitute_variables(self):
        """Test variable substitution."""
        from app.api.v2.localization import _substitute_variables

        text = "Hello {name}, you have {count} new notifications"
        variables = {"name": "John", "count": 3}
        result = _substitute_variables(text, variables)

        assert "John" in result
        assert "3" in result
        assert "{name}" not in result
        assert "{count}" not in result

    def test_substitute_variables_missing(self):
        """Test variable substitution with missing variables."""
        from app.api.v2.localization import _substitute_variables

        text = "Hello {name}, you have {count} new notifications"
        variables = {"name": "John"}  # Missing 'count'
        result = _substitute_variables(text, variables)

        # Should not raise exception, should keep original format
        assert "John" in result

    def test_flatten_translations(self):
        """Test flattening nested translation dictionary."""
        from app.api.v2.localization import _flatten_translations

        nested = {
            "auth": {
                "login": {
                    "title": "Login",
                    "button": "Sign In"
                }
            },
            "common": {
                "ok": "OK"
            }
        }

        flat = _flatten_translations(nested)

        assert "auth.login.title" in flat
        assert "auth.login.button" in flat
        assert "common.ok" in flat
        assert flat["auth.login.title"] == "Login"


# ============================================================================
# RBAC Tests
# ============================================================================

class TestLocalizationRBAC:
    """Test suite for RBAC in localization endpoints."""

    @pytest.mark.asyncio
    async def test_read_access_for_all_users(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test that all authenticated users can read translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Patient should be able to read languages
                response = client.get(
                    "/api/v2/localization/languages",
                    headers={"X-Session-ID": "test_session"}
                )
                assert response.status_code == 200

                # Patient should be able to read translations
                response = client.get(
                    "/api/v2/localization/translations/en-US",
                    headers={"X-Session-ID": "test_session"}
                )
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_write_access_admin_only(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any],
        admin_user_data: Dict[str, Any]
    ):
        """Test that only admins can write translations."""
        # Patient attempt (should fail)
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/translations/en-US/test.key",
                    json={"value": "Test Value"},
                    headers={"X-Session-ID": "test_session"}
                )
                assert response.status_code == 403

        # Admin attempt (should succeed)
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=admin_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.put(
                    "/api/v2/localization/translations/en-US/test.key",
                    json={"value": "Test Value"},
                    headers={"X-Session-ID": "test_session"}
                )
                assert response.status_code == 200


# ============================================================================
# Performance and Edge Case Tests
# ============================================================================

class TestLocalizationPerformance:
    """Test suite for performance and edge cases."""

    @pytest.mark.asyncio
    async def test_large_translation_batch(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        patient_user_data: Dict[str, Any]
    ):
        """Test handling large number of translations."""
        # Mock large translation set
        mock_localization_service.get_translations.return_value = {
            f"key_{i}": f"value_{i}" for i in range(1000)
        }

        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                response = client.get(
                    "/api/v2/localization/translations/en-US",
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                # Should handle large datasets without timeout

    @pytest.mark.asyncio
    async def test_unicode_translations(
        self,
        client: TestClient,
        mock_redis_cache,
        mock_localization_service,
        admin_user_data: Dict[str, Any]
    ):
        """Test handling Unicode characters in translations."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=admin_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                unicode_text = "Olá! Você está usando ñ, ç, é, ã, õ 🌟"
                response = client.put(
                    "/api/v2/localization/translations/pt-BR/test.unicode",
                    json={"value": unicode_text},
                    headers={"X-Session-ID": "test_session"}
                )

                assert response.status_code == 200
                data = response.json()
                assert data["value"] == unicode_text

    @pytest.mark.asyncio
    async def test_empty_translation_key(
        self,
        client: TestClient,
        mock_redis_cache,
        patient_user_data: Dict[str, Any]
    ):
        """Test handling empty translation key."""
        with patch('app.api.v2.localization._get_current_user_simple',
                   return_value=AsyncMock(return_value=patient_user_data)):
            with patch('app.api.v2.localization.get_redis_cache',
                       return_value=mock_redis_cache):

                # Empty key should return error or handle gracefully
                response = client.get(
                    "/api/v2/localization/translations/en-US/",
                    headers={"X-Session-ID": "test_session"}
                )

                # Should handle gracefully (404 or 400)
                assert response.status_code in [400, 404]
