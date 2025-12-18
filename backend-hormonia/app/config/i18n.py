"""
Internationalization (i18n) Configuration Module

Provides lightweight i18n support for error messages and user-facing text.
Supports Portuguese (pt-BR) and English (en-US) with fallback mechanisms.

Features:
- Locale detection from query params, headers, cookies
- Translation with variable substitution
- Fallback to default locale (pt-BR)
- JSON-based translation files
- Thread-safe translation access
"""

import i18n
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Setup i18n library
i18n.set("filename_format", "{locale}.{format}")
i18n.set("file_format", "json")
i18n.set("fallback", "pt-BR")  # Default to Portuguese
i18n.set("locale", "pt-BR")
i18n.set("enable_memoization", True)  # Cache translations for performance
i18n.set("skip_locale_root_data", True)  # Allow nested keys

# Load translation files from app/locales directory
LOCALES_DIR = Path(__file__).parent.parent / "locales"
i18n.load_path.append(str(LOCALES_DIR))

# Available locales
SUPPORTED_LOCALES = ["pt-BR", "en-US"]
DEFAULT_LOCALE = "pt-BR"

# Translation namespaces (top-level keys in translation files)
NAMESPACES = ["errors", "success", "validation", "common"]


def get_locale_from_request(request) -> str:
    """
    Determine locale from request with priority:
    1. Query parameter: ?lang=en-US
    2. Header: Accept-Language: en-US
    3. Cookie: locale=en-US
    4. Default: pt-BR

    Args:
        request: FastAPI Request object

    Returns:
        Locale code (e.g., 'pt-BR', 'en-US')
    """
    # 1. Query parameter (highest priority for explicit choice)
    if hasattr(request, "query_params"):
        lang = request.query_params.get("lang")
        if lang and lang in SUPPORTED_LOCALES:
            return lang

    # 2. Accept-Language header
    if hasattr(request, "headers"):
        accept_lang = request.headers.get("Accept-Language", "")
        # Simple parsing: check if 'en' or 'pt' is in header
        if "en" in accept_lang.lower():
            return "en-US"
        if "pt" in accept_lang.lower():
            return "pt-BR"

    # 3. Cookie
    if hasattr(request, "cookies"):
        locale_cookie = request.cookies.get("locale")
        if locale_cookie and locale_cookie in SUPPORTED_LOCALES:
            return locale_cookie

    # 4. Default fallback
    return DEFAULT_LOCALE


def set_locale(locale: str) -> None:
    """
    Set current locale for i18n library.

    Args:
        locale: Locale code (e.g., 'pt-BR', 'en-US')
    """
    if locale in SUPPORTED_LOCALES:
        i18n.set("locale", locale)
        logger.debug(f"Locale set to: {locale}")
    else:
        logger.warning(f"Invalid locale '{locale}', using default: {DEFAULT_LOCALE}")
        i18n.set("locale", DEFAULT_LOCALE)


def get_current_locale() -> str:
    """
    Get currently active locale.

    Returns:
        Current locale code
    """
    return i18n.get("locale")


def t(key: str, **kwargs) -> str:
    """
    Translate key with optional variable substitution.

    Args:
        key: Translation key (e.g., 'errors.patient.not_found')
        **kwargs: Variables for substitution (e.g., patient_id='123')

    Returns:
        Translated string with variables substituted

    Examples:
        >>> t('errors.patient.not_found')
        'Paciente não encontrado'

        >>> t('errors.patient.duplicate_cpf', cpf='123.456.789-00')
        'CPF 123.456.789-00 já cadastrado'
    """
    try:
        # Get translation with variable substitution
        translated = i18n.t(key, **kwargs)

        # If translation key not found, i18n returns the key itself
        # Log warning for missing translations
        if translated == key:
            logger.warning(
                f"Missing translation for key: {key} (locale: {get_current_locale()})"
            )

        return translated
    except Exception as e:
        logger.error(f"Error translating key '{key}': {e}")
        return key  # Return key as fallback


def translate_dict(key_prefix: str, data: Dict[str, Any]) -> Dict[str, str]:
    """
    Translate multiple keys with same prefix.

    Args:
        key_prefix: Prefix for translation keys (e.g., 'errors.validation')
        data: Dictionary with keys to append to prefix

    Returns:
        Dictionary with translated values

    Example:
        >>> translate_dict('errors.validation', {'required': None, 'invalid_email': None})
        {'required': 'Campo obrigatório', 'invalid_email': 'Email inválido'}
    """
    result = {}
    for key in data.keys():
        full_key = f"{key_prefix}.{key}"
        result[key] = t(full_key)
    return result


def get_available_locales() -> list:
    """
    Get list of available locales with metadata.

    Returns:
        List of locale dictionaries with code, name, and is_default
    """
    return [
        {
            "code": "pt-BR",
            "name": "Português (Brasil)",
            "native_name": "Português (Brasil)",
            "is_default": True,
        },
        {
            "code": "en-US",
            "name": "English (United States)",
            "native_name": "English (United States)",
            "is_default": False,
        },
    ]


def validate_locale(locale: str) -> bool:
    """
    Check if locale is supported.

    Args:
        locale: Locale code to validate

    Returns:
        True if locale is supported, False otherwise
    """
    return locale in SUPPORTED_LOCALES


# Initialize i18n on module load
logger.info(
    f"i18n initialized with locales: {SUPPORTED_LOCALES}, default: {DEFAULT_LOCALE}"
)
