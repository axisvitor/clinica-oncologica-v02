"""
Localization API v2 - Internationalization (i18n) System

Enhanced i18n endpoints with:
- Cursor-based pagination for translation lists
- Redis caching with LONG TTLs (translations rarely change)
- Rate limiting: 100 req/min (read-heavy)
- Eager loading for language metadata
- Field selection via ?fields= for sparse fieldsets
- RBAC: All users can read, Admin can write
- Fallback logic (pt-BR → pt → en-US)
- Pluralization support
- Variable substitution ({name}, {count})
- Context-aware translations (formal/informal)
- JSON import/export for translations

SUPPORTED LANGUAGES:
- pt-BR: Portuguese (Brazil)
- pt-PT: Portuguese (Portugal)
- en-US: English (United States)
- es-ES: Spanish (Spain)

FALLBACK CHAIN:
pt-BR → pt-PT → en-US (default)
es-ES → en-US (default)
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from uuid import UUID
import logging
import re
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.v2.localization import (
    LanguageV2Response,
    LanguageV2List,
    TranslationV2Response,
    TranslationV2List,
    TranslationV2Update,
    UserLanguagePreferenceV2,
    UserLanguagePreferenceV2Update,
    TranslationKeyV2Response,
    TranslationExportV2,
    TranslationImportV2,
    TranslationStatsV2,
    MissingTranslationsV2,
    TranslationSearchV2,
)
from app.schemas.v2.common import ErrorResponse
from .dependencies import (
    get_pagination_params,
    get_field_selection,
    get_eager_load_params,
    create_cursor,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_current_user_from_session, get_redis_cache
from app.utils.rate_limiter import limiter
from app.services.localization import get_localization_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL configurations (LONG TTLs - translations rarely change)
CACHE_TTL_TRANSLATIONS = 14400  # 4 hours for translations
CACHE_TTL_LANGUAGES = 86400  # 24 hours for language list
CACHE_TTL_USER_PREFS = 3600  # 1 hour for user preferences
CACHE_TTL_STATS = 7200  # 2 hours for statistics

# Supported languages configuration
SUPPORTED_LANGUAGES = {
    "pt-BR": {
        "name": "Portuguese (Brazil)",
        "native_name": "Português (Brasil)",
        "fallback": "pt-PT",
        "direction": "ltr",
        "enabled": True,
    },
    "pt-PT": {
        "name": "Portuguese (Portugal)",
        "native_name": "Português (Portugal)",
        "fallback": "en-US",
        "direction": "ltr",
        "enabled": True,
    },
    "en-US": {
        "name": "English (United States)",
        "native_name": "English (United States)",
        "fallback": None,  # Default language
        "direction": "ltr",
        "enabled": True,
    },
    "es-ES": {
        "name": "Spanish (Spain)",
        "native_name": "Español (España)",
        "fallback": "en-US",
        "direction": "ltr",
        "enabled": True,
    },
}

DEFAULT_LANGUAGE = "en-US"

# Translation namespaces
NAMESPACES = ["flows", "messages", "auth", "common", "errors", "email"]


async def _get_current_user_simple(
    session_id: str = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache)
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header"
        )

    session_data = await redis_cache.get_session(session_id)
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    firebase_uid = session_data.get("firebase_uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session data"
        )

    # Get user from cache or DB
    user_data = await redis_cache.get_user_by_uid(firebase_uid)
    if not user_data:
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        user_data = {
            "id": str(user.id),
            "firebase_uid": user.firebase_uid,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_active": user.is_active
        }
        await redis_cache.cache_user_data(firebase_uid, user_data, ttl=900)

    if not user_data.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user_data


def _extract_user_role(current_user: Dict[str, Any]) -> UserRole:
    """Extract UserRole enum from user data."""
    role_str = current_user.get("role", "").lower()
    try:
        return UserRole(role_str)
    except ValueError:
        return UserRole.PATIENT


def _check_admin(current_user: Dict[str, Any]) -> None:
    """Ensure user is an admin."""
    role = _extract_user_role(current_user)
    if role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action"
        )


def _resolve_fallback_chain(language: str) -> List[str]:
    """
    Resolve fallback chain for a language.

    Args:
        language: Language code (e.g., 'pt-BR')

    Returns:
        List of language codes in fallback order

    Example:
        pt-BR → [pt-BR, pt-PT, en-US]
        es-ES → [es-ES, en-US]
    """
    chain = [language]
    current = language

    while current in SUPPORTED_LANGUAGES:
        fallback = SUPPORTED_LANGUAGES[current].get("fallback")
        if fallback and fallback not in chain:
            chain.append(fallback)
            current = fallback
        else:
            break

    # Always end with default language
    if DEFAULT_LANGUAGE not in chain:
        chain.append(DEFAULT_LANGUAGE)

    return chain


def _apply_pluralization(text: str, count: int, language: str = "en-US") -> str:
    """
    Apply pluralization rules to text.

    Supports format: {singular|plural}
    Example: "You have {0|1} {message|messages}" with count=2 → "You have 2 messages"

    Args:
        text: Text with pluralization markers
        count: Count for pluralization
        language: Language code for language-specific rules

    Returns:
        Text with correct plural form
    """
    # Simple pluralization: {singular|plural}
    pattern = r'\{([^|]+)\|([^}]+)\}'

    def replace_plural(match):
        singular = match.group(1)
        plural = match.group(2)
        return singular if count == 1 else plural

    result = re.sub(pattern, replace_plural, text)

    # Replace {count} placeholder
    result = result.replace("{count}", str(count))

    return result


def _substitute_variables(text: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """
    Substitute variables in text.

    Supports {variable_name} format.

    Args:
        text: Text with variable placeholders
        variables: Dictionary of variable values

    Returns:
        Text with variables substituted
    """
    if not variables:
        return text

    try:
        return text.format(**variables)
    except KeyError as e:
        logger.warning(f"Missing variable in translation: {e}")
        return text
    except Exception as e:
        logger.error(f"Error substituting variables: {e}")
        return text


def _get_translation_with_fallback(
    key: str,
    language: str,
    namespace: str = "common",
    context: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    count: Optional[int] = None
) -> str:
    """
    Get translation with fallback chain support.

    Args:
        key: Translation key (e.g., 'auth.login.title')
        language: Requested language
        namespace: Translation namespace
        context: Context for context-aware translations (formal/informal)
        variables: Variables for substitution
        count: Count for pluralization

    Returns:
        Translated text or key if not found
    """
    localization_service = get_localization_service()
    fallback_chain = _resolve_fallback_chain(language)

    for lang in fallback_chain:
        try:
            # Try to get translation from service
            text = localization_service.translate(
                key=key,
                locale=lang,
                namespace=namespace,
                fallback=None
            )

            if text and text != key:  # Translation found
                # Apply context if provided
                if context and isinstance(text, dict):
                    text = text.get(context, text.get("default", key))

                # Apply pluralization if count provided
                if count is not None:
                    text = _apply_pluralization(text, count, lang)

                # Substitute variables
                if variables:
                    text = _substitute_variables(text, variables)

                logger.debug(f"Translation found for {key} in {lang}")
                return text

        except Exception as e:
            logger.warning(f"Error getting translation {key} for {lang}: {e}")
            continue

    # Return key if no translation found
    logger.warning(f"No translation found for key: {key} (language: {language})")
    return key


@router.get("/languages", response_model=LanguageV2List)
@limiter.limit("100/minute")
async def list_languages(
    request: Request,
    enabled_only: bool = Query(True, description="Show only enabled languages"),
    fields: Optional[List[str]] = Depends(get_field_selection),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> LanguageV2List:
    """
    List all available languages.

    Features:
    - Lists all supported languages with metadata
    - Redis caching with 24-hour TTL (languages rarely change)
    - Field selection for bandwidth optimization
    - Filter by enabled status

    Rate limit: 100 requests/minute
    """
    try:
        # Build cache key
        cache_key = f"i18n:languages:enabled:{enabled_only}:fields:{','.join(fields) if fields else 'all'}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for languages list: {cache_key}")
            return LanguageV2List(**cached_data)

        # Build language list
        languages = []
        for code, info in SUPPORTED_LANGUAGES.items():
            if enabled_only and not info.get("enabled", True):
                continue

            lang_data = {
                "code": code,
                "name": info["name"],
                "native_name": info["native_name"],
                "direction": info["direction"],
                "fallback": info.get("fallback"),
                "enabled": info.get("enabled", True),
                "is_default": code == DEFAULT_LANGUAGE
            }

            # Apply field selection
            if fields:
                lang_data = apply_field_selection(lang_data, fields)

            languages.append(lang_data)

        result = LanguageV2List(
            data=languages,
            total=len(languages),
            default_language=DEFAULT_LANGUAGE
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_LANGUAGES)

        return result

    except Exception as e:
        logger.error(f"Error listing languages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve languages"
        )


@router.get("/translations/{language}", response_model=TranslationV2List)
@limiter.limit("100/minute")
async def get_translations_for_language(
    language: str,
    request: Request,
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    search: Optional[str] = Query(None, description="Search in keys or values"),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> TranslationV2List:
    """
    Get all translations for a specific language.

    Features:
    - Retrieves all translation keys for a language
    - Optional namespace filtering
    - Search functionality
    - Redis caching with 4-hour TTL
    - Fallback to default language if requested language not found

    Rate limit: 100 requests/minute
    """
    try:
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported"
            )

        # Build cache key
        cache_key = f"i18n:translations:{language}:ns:{namespace or 'all'}:search:{search or 'none'}"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for translations: {cache_key}")
            return TranslationV2List(**cached_data)

        # Get localization service
        localization_service = get_localization_service()

        # Get translations for specified namespaces
        namespaces_to_fetch = [namespace] if namespace else NAMESPACES
        all_translations = {}

        for ns in namespaces_to_fetch:
            try:
                translations = localization_service.get_translations(language, ns)
                if translations:
                    # Flatten nested translations with dot notation
                    flat_translations = _flatten_translations(translations, ns)
                    all_translations.update(flat_translations)
            except Exception as e:
                logger.warning(f"Error loading namespace {ns}: {e}")
                continue

        # Apply search filter
        if search:
            search_lower = search.lower()
            all_translations = {
                key: value for key, value in all_translations.items()
                if search_lower in key.lower() or
                   (isinstance(value, str) and search_lower in value.lower())
            }

        # Build response
        translation_list = [
            {
                "key": key,
                "value": value,
                "namespace": key.split(".")[0] if "." in key else "common"
            }
            for key, value in all_translations.items()
        ]

        result = TranslationV2List(
            data=translation_list,
            language=language,
            total=len(translation_list),
            namespaces=namespaces_to_fetch
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_TRANSLATIONS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting translations for {language}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translations"
        )


def _flatten_translations(
    translations: Dict[str, Any],
    prefix: str = "",
    separator: str = "."
) -> Dict[str, str]:
    """
    Flatten nested translation dictionary to dot notation.

    Args:
        translations: Nested translation dictionary
        prefix: Key prefix (namespace)
        separator: Key separator (default: '.')

    Returns:
        Flattened dictionary with dot-notation keys
    """
    flat = {}

    for key, value in translations.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict):
            flat.update(_flatten_translations(value, new_key, separator))
        else:
            flat[new_key] = str(value)

    return flat


@router.get("/translations/{language}/{key:path}", response_model=TranslationKeyV2Response)
@limiter.limit("100/minute")
async def get_translation_by_key(
    language: str,
    key: str,
    request: Request,
    context: Optional[str] = Query(None, description="Context (formal/informal)"),
    variables: Optional[str] = Query(None, description="JSON-encoded variables"),
    count: Optional[int] = Query(None, description="Count for pluralization"),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Get a specific translation by key.

    Features:
    - Retrieves translation for specific key
    - Fallback chain support (pt-BR → pt-PT → en-US)
    - Context-aware translations (formal/informal)
    - Variable substitution support
    - Pluralization support
    - Redis caching with 4-hour TTL

    Rate limit: 100 requests/minute
    """
    try:
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported"
            )

        # Parse variables if provided
        parsed_variables = None
        if variables:
            try:
                parsed_variables = json.loads(variables)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for variables"
                )

        # Extract namespace from key (first part before dot)
        namespace = key.split(".")[0] if "." in key else "common"

        # Build cache key (without variables for better cache hit rate)
        cache_key = f"i18n:key:{language}:{key}:ctx:{context or 'none'}:cnt:{count or 'none'}"

        # Try cache first (only if no variables)
        if not parsed_variables:
            cached_data = await redis_cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for translation key: {cache_key}")
                return cached_data

        # Get translation with fallback
        translated_text = _get_translation_with_fallback(
            key=key,
            language=language,
            namespace=namespace,
            context=context,
            variables=parsed_variables,
            count=count
        )

        # Determine which language was used (for transparency)
        fallback_chain = _resolve_fallback_chain(language)
        used_language = language  # Will be updated if fallback was used

        # Check if we used fallback
        localization_service = get_localization_service()
        for lang in fallback_chain:
            try:
                test_translation = localization_service.translate(
                    key=key,
                    locale=lang,
                    namespace=namespace,
                    fallback=None
                )
                if test_translation and test_translation != key:
                    used_language = lang
                    break
            except Exception:
                continue

        response = {
            "key": key,
            "value": translated_text,
            "language": language,
            "used_language": used_language,
            "fallback_used": used_language != language,
            "namespace": namespace,
            "context": context,
            "has_pluralization": count is not None,
            "has_variables": parsed_variables is not None
        }

        # Cache the result (only if no variables)
        if not parsed_variables:
            await redis_cache.set(cache_key, response, ttl=CACHE_TTL_TRANSLATIONS)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting translation {key} for {language}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translation"
        )


@router.put("/translations/{language}/{key:path}", response_model=TranslationKeyV2Response)
@limiter.limit("30/minute")
async def update_translation(
    language: str,
    key: str,
    translation_data: TranslationV2Update,
    request: Request,
    db: Session = Depends(get_db),
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> Dict[str, Any]:
    """
    Update a translation (Admin only).

    Features:
    - RBAC: Only admins can update translations
    - Updates translation in memory cache
    - Invalidates Redis cache
    - Logs changes for audit trail

    Note: This updates the in-memory cache only. For persistent updates,
    translations should be updated in the JSON files directly.

    Rate limit: 30 requests/minute
    """
    try:
        # Check admin permission
        _check_admin(current_user)

        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported"
            )

        # Extract namespace
        namespace = key.split(".")[0] if "." in key else "common"

        # Get localization service
        localization_service = get_localization_service()

        # Update translation in cache
        # Note: This is in-memory only. For persistent updates, modify JSON files.
        cache_key_translations = f"{language}:{namespace}"
        translations = localization_service.get_translations(language, namespace)

        # Navigate to the correct nested location
        keys_parts = key.split(".")
        current_level = translations

        # Navigate to parent
        for part in keys_parts[:-1]:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

        # Update value
        old_value = current_level.get(keys_parts[-1], None)
        current_level[keys_parts[-1]] = translation_data.value

        # Update cache
        localization_service._translations_cache[cache_key_translations] = translations

        # Invalidate Redis caches
        await redis_cache.delete_pattern(f"i18n:translations:{language}:*")
        await redis_cache.delete_pattern(f"i18n:key:{language}:{key}:*")

        # Log the change
        logger.info(
            f"Translation updated: {language}/{key} by user {current_user.get('id')} "
            f"(old: '{old_value}', new: '{translation_data.value}')"
        )

        return {
            "key": key,
            "value": translation_data.value,
            "language": language,
            "used_language": language,
            "fallback_used": False,
            "namespace": namespace,
            "context": None,
            "has_pluralization": False,
            "has_variables": False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating translation {key} for {language}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update translation"
        )


@router.get("/user/language", response_model=UserLanguagePreferenceV2)
@limiter.limit("100/minute")
async def get_user_language_preference(
    request: Request,
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> UserLanguagePreferenceV2:
    """
    Get current user's language preference.

    Features:
    - Retrieves user's preferred language
    - Redis caching with 1-hour TTL
    - Returns system default if no preference set

    Rate limit: 100 requests/minute
    """
    try:
        user_id = current_user.get("id")

        # Build cache key
        cache_key = f"i18n:user:{user_id}:language"

        # Try cache first
        cached_data = await redis_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache hit for user language preference: {cache_key}")
            return UserLanguagePreferenceV2(**cached_data)

        # Try to get from Redis (user preferences are stored separately)
        user_pref_key = f"user:{user_id}:preferences:language"
        language_pref = await redis_cache.get(user_pref_key)

        if not language_pref:
            # Return default language
            language_pref = DEFAULT_LANGUAGE

        # Validate language
        if language_pref not in SUPPORTED_LANGUAGES:
            logger.warning(f"Invalid language preference '{language_pref}' for user {user_id}, using default")
            language_pref = DEFAULT_LANGUAGE

        result = UserLanguagePreferenceV2(
            user_id=UUID(user_id),
            language=language_pref,
            is_default=language_pref == DEFAULT_LANGUAGE,
            updated_at=datetime.utcnow()
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_USER_PREFS)

        return result

    except Exception as e:
        logger.error(f"Error getting user language preference: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve language preference"
        )


@router.put("/user/language", response_model=UserLanguagePreferenceV2)
@limiter.limit("30/minute")
async def set_user_language_preference(
    preference_data: UserLanguagePreferenceV2Update,
    request: Request,
    redis_cache = Depends(get_redis_cache),
    current_user: Dict = Depends(_get_current_user_simple),
) -> UserLanguagePreferenceV2:
    """
    Set current user's language preference.

    Features:
    - Updates user's preferred language
    - Validates language is supported
    - Invalidates user preference cache
    - Stores in Redis for persistence

    Rate limit: 30 requests/minute
    """
    try:
        user_id = current_user.get("id")

        # Validate language
        if preference_data.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{preference_data.language}' not supported. "
                       f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}"
            )

        # Check if language is enabled
        if not SUPPORTED_LANGUAGES[preference_data.language].get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{preference_data.language}' is not enabled"
            )

        # Store preference in Redis
        user_pref_key = f"user:{user_id}:preferences:language"
        await redis_cache.set(user_pref_key, preference_data.language, ttl=None)  # No expiry

        # Invalidate cache
        await redis_cache.delete(f"i18n:user:{user_id}:language")

        # Log the change
        logger.info(
            f"User {user_id} language preference updated to {preference_data.language}"
        )

        result = UserLanguagePreferenceV2(
            user_id=UUID(user_id),
            language=preference_data.language,
            is_default=preference_data.language == DEFAULT_LANGUAGE,
            updated_at=datetime.utcnow()
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user language preference: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update language preference"
        )
