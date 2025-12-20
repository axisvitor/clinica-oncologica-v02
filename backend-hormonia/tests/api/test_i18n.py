"""
Internationalization (i18n) Tests

Tests for error message translation and locale detection.

NOTE: Requires python-i18n package to be installed.
"""

import pytest

# Skip entire module if i18n is not installed
pytest.importorskip("i18n", reason="python-i18n not installed")

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.config.i18n import (
    t,
    set_locale,
    get_current_locale,
    get_locale_from_request,
    validate_locale,
    SUPPORTED_LOCALES,
    DEFAULT_LOCALE
)
from app.exceptions.i18n_exceptions import (
    PatientNotFoundException,
    DuplicateCPFException,
    InvalidCredentialsException,
    QuizSessionExpiredException,
    SagaTimeoutException,
    RequiredFieldException,
)


class TestI18nConfiguration:
    """Test i18n configuration and utilities."""

    def test_default_locale(self):
        """Test default locale is pt-BR."""
        assert DEFAULT_LOCALE == 'pt-BR'

    def test_supported_locales(self):
        """Test supported locales include pt-BR and en-US."""
        assert 'pt-BR' in SUPPORTED_LOCALES
        assert 'en-US' in SUPPORTED_LOCALES

    def test_validate_locale(self):
        """Test locale validation."""
        assert validate_locale('pt-BR') is True
        assert validate_locale('en-US') is True
        assert validate_locale('fr-FR') is False
        assert validate_locale('invalid') is False

    def test_set_and_get_locale(self):
        """Test setting and getting locale."""
        # Save current locale
        original_locale = get_current_locale()

        # Test setting locale
        set_locale('en-US')
        assert get_current_locale() == 'en-US'

        set_locale('pt-BR')
        assert get_current_locale() == 'pt-BR'

        # Restore original locale
        set_locale(original_locale)


class TestTranslationFunction:
    """Test translation function."""

    def test_translate_simple_key(self):
        """Test translating simple key without variables."""
        set_locale('pt-BR')
        message = t('errors.patient.not_found')
        assert 'Paciente não encontrado' in message

        set_locale('en-US')
        message = t('errors.patient.not_found')
        assert 'Patient not found' in message

    def test_translate_with_variables(self):
        """Test translating key with variable substitution."""
        set_locale('pt-BR')
        message = t('errors.patient.duplicate_cpf', cpf='123.456.789-00')
        assert '123.456.789-00' in message
        assert 'CPF' in message

        set_locale('en-US')
        message = t('errors.patient.duplicate_cpf', cpf='123.456.789-00')
        assert '123.456.789-00' in message
        assert 'CPF' in message

    def test_translate_missing_key(self):
        """Test translating non-existent key returns key itself."""
        message = t('errors.nonexistent.key')
        assert message == 'errors.nonexistent.key'

    def test_translate_success_messages(self):
        """Test translating success messages."""
        set_locale('pt-BR')
        message = t('success.patient_created')
        assert 'sucesso' in message.lower()

        set_locale('en-US')
        message = t('success.patient_created')
        assert 'success' in message.lower()


class TestLocaleDetection:
    """Test locale detection from request."""

    def test_locale_from_query_param(self):
        """Test locale detection from query parameter."""
        # Mock request with query parameter
        request = MagicMock()
        request.query_params = {'lang': 'en-US'}
        request.headers = {}
        request.cookies = {}

        locale = get_locale_from_request(request)
        assert locale == 'en-US'

    def test_locale_from_header(self):
        """Test locale detection from Accept-Language header."""
        # Mock request with header
        request = MagicMock()
        request.query_params = {}
        request.headers = {'Accept-Language': 'en-US,en;q=0.9'}
        request.cookies = {}

        locale = get_locale_from_request(request)
        assert locale == 'en-US'

    def test_locale_from_cookie(self):
        """Test locale detection from cookie."""
        # Mock request with cookie
        request = MagicMock()
        request.query_params = {}
        request.headers = {}
        request.cookies = {'locale': 'en-US'}

        locale = get_locale_from_request(request)
        assert locale == 'en-US'

    def test_locale_priority(self):
        """Test locale detection priority: query > header > cookie."""
        # Query parameter has highest priority
        request = MagicMock()
        request.query_params = {'lang': 'en-US'}
        request.headers = {'Accept-Language': 'pt-BR'}
        request.cookies = {'locale': 'pt-BR'}

        locale = get_locale_from_request(request)
        assert locale == 'en-US'

    def test_locale_fallback_to_default(self):
        """Test locale fallback to default when none provided."""
        request = MagicMock()
        request.query_params = {}
        request.headers = {}
        request.cookies = {}

        locale = get_locale_from_request(request)
        assert locale == DEFAULT_LOCALE


class TestTranslatableExceptions:
    """Test translatable exception classes."""

    def test_patient_not_found_exception_pt_br(self):
        """Test PatientNotFoundException in Portuguese."""
        set_locale('pt-BR')

        with pytest.raises(PatientNotFoundException) as exc_info:
            raise PatientNotFoundException(patient_id='123')

        assert exc_info.value.status_code == 404
        assert 'não encontrado' in str(exc_info.value.detail).lower()

    def test_patient_not_found_exception_en_us(self):
        """Test PatientNotFoundException in English."""
        set_locale('en-US')

        with pytest.raises(PatientNotFoundException) as exc_info:
            raise PatientNotFoundException(patient_id='123')

        assert exc_info.value.status_code == 404
        assert 'not found' in str(exc_info.value.detail).lower()

    def test_duplicate_cpf_exception(self):
        """Test DuplicateCPFException with variable substitution."""
        set_locale('pt-BR')

        with pytest.raises(DuplicateCPFException) as exc_info:
            raise DuplicateCPFException(cpf='123.456.789-00')

        assert exc_info.value.status_code == 409
        assert '123.456.789-00' in str(exc_info.value.detail)

    def test_invalid_credentials_exception(self):
        """Test InvalidCredentialsException."""
        set_locale('pt-BR')

        with pytest.raises(InvalidCredentialsException) as exc_info:
            raise InvalidCredentialsException()

        assert exc_info.value.status_code == 401
        assert 'inválid' in str(exc_info.value.detail).lower()

    def test_quiz_session_expired_exception(self):
        """Test QuizSessionExpiredException."""
        set_locale('en-US')

        with pytest.raises(QuizSessionExpiredException) as exc_info:
            raise QuizSessionExpiredException()

        assert exc_info.value.status_code == 410
        assert 'expired' in str(exc_info.value.detail).lower()

    def test_saga_timeout_exception(self):
        """Test SagaTimeoutException with timeout parameter."""
        set_locale('pt-BR')

        with pytest.raises(SagaTimeoutException) as exc_info:
            raise SagaTimeoutException(timeout=30)

        assert exc_info.value.status_code == 408
        assert '30' in str(exc_info.value.detail)

    def test_required_field_exception(self):
        """Test RequiredFieldException."""
        set_locale('en-US')

        with pytest.raises(RequiredFieldException) as exc_info:
            raise RequiredFieldException(field='email')

        assert exc_info.value.status_code == 422
        assert 'email' in str(exc_info.value.detail).lower()
        assert 'required' in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
class TestI18nMiddleware:
    """Test i18n middleware."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with i18n middleware."""
        from fastapi import FastAPI, Request
        from app.middleware.i18n_middleware import i18n_middleware
        from app.config.i18n import get_current_locale

        app = FastAPI()
        app.middleware("http")(i18n_middleware)

        @app.get("/test-locale")
        async def test_endpoint(request: Request):
            return {
                "locale": get_current_locale(),
                "state_locale": getattr(request.state, 'locale', None)
            }

        return app

    async def test_middleware_sets_locale_from_query(self, app):
        """Test middleware sets locale from query parameter."""
        client = TestClient(app)
        response = client.get("/test-locale?lang=en-US")

        assert response.status_code == 200
        data = response.json()
        assert data["locale"] == "en-US"
        assert data["state_locale"] == "en-US"
        assert response.headers["Content-Language"] == "en-US"

    async def test_middleware_sets_locale_from_header(self, app):
        """Test middleware sets locale from Accept-Language header."""
        client = TestClient(app)
        response = client.get(
            "/test-locale",
            headers={"Accept-Language": "en-US,en;q=0.9"}
        )

        assert response.status_code == 200
        assert response.headers["Content-Language"] == "en-US"

    async def test_middleware_adds_content_language_header(self, app):
        """Test middleware adds Content-Language header to response."""
        client = TestClient(app)
        response = client.get("/test-locale")

        assert "Content-Language" in response.headers
        assert response.headers["Content-Language"] in SUPPORTED_LOCALES


class TestPydanticI18n:
    """Test Pydantic validation error translation."""

    def test_translate_pydantic_errors(self):
        """Test translating Pydantic validation errors."""
        from pydantic import BaseModel, EmailStr, ValidationError
        from app.utils.pydantic_i18n import translate_pydantic_errors

        class TestModel(BaseModel):
            email: EmailStr
            name: str

        set_locale('pt-BR')

        try:
            TestModel(email='invalid-email', name='')
        except ValidationError as e:
            translated = translate_pydantic_errors(e)

            assert 'errors' in translated
            assert len(translated['errors']) > 0

            # Check that errors have required fields
            for error in translated['errors']:
                assert 'field' in error
                assert 'message' in error
                assert 'type' in error

    def test_get_first_error_message(self):
        """Test getting first error message from Pydantic errors."""
        from pydantic import BaseModel, EmailStr, ValidationError
        from app.utils.pydantic_i18n import get_first_error_message

        class TestModel(BaseModel):
            email: EmailStr

        try:
            TestModel(email='invalid')
        except ValidationError as e:
            message = get_first_error_message(e)
            assert isinstance(message, str)
            assert len(message) > 0


class TestCommonTranslations:
    """Test common UI translations."""

    def test_common_buttons_pt_br(self):
        """Test common button translations in Portuguese."""
        set_locale('pt-BR')

        assert t('common.save') == 'Salvar'
        assert t('common.cancel') == 'Cancelar'
        assert t('common.delete') == 'Excluir'
        assert t('common.confirm') == 'Confirmar'

    def test_common_buttons_en_us(self):
        """Test common button translations in English."""
        set_locale('en-US')

        assert t('common.save') == 'Save'
        assert t('common.cancel') == 'Cancel'
        assert t('common.delete') == 'Delete'
        assert t('common.confirm') == 'Confirm'

    def test_common_states(self):
        """Test common state translations."""
        set_locale('pt-BR')

        assert 'Carregando' in t('common.loading')
        assert 'Salvando' in t('common.saving')

        set_locale('en-US')

        assert 'Loading' in t('common.loading')
        assert 'Saving' in t('common.saving')


@pytest.mark.integration
class TestI18nIntegration:
    """Integration tests for i18n system."""

    def test_end_to_end_error_flow(self):
        """Test complete error flow with i18n."""
        # Simulate request with English locale
        set_locale('en-US')

        # Raise translatable exception
        try:
            raise PatientNotFoundException(patient_id='test-123')
        except PatientNotFoundException as e:
            # Verify exception has correct status and translated message
            assert e.status_code == 404
            assert 'not found' in str(e.detail).lower()

    def test_locale_switching(self):
        """Test switching locales mid-request."""
        # Start with Portuguese
        set_locale('pt-BR')
        pt_message = t('errors.patient.not_found')
        assert 'não encontrado' in pt_message.lower()

        # Switch to English
        set_locale('en-US')
        en_message = t('errors.patient.not_found')
        assert 'not found' in en_message.lower()

        # Verify messages are different
        assert pt_message != en_message
