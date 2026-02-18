"""
Localization API v2 - i18n system with Redis caching, fallback chains, pluralization.
Supports: pt-BR, pt-PT, en-US, es-ES. Rate limit: 100 req/min.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID
import logging
import re
import json
import sys
import inspect

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Header

from app.database import get_db
from app.models.user import UserRole
from app.schemas.v2.localization import (
    LanguageV2List,
    TranslationV2List,
    TranslationV2Update,
    UserLanguagePreferenceV2,
    UserLanguagePreferenceV2Update,
    TranslationKeyV2Response,
)
from app.api.v2.dependencies import (
    get_field_selection,
    apply_field_selection,
)
from app.dependencies.auth_dependencies import get_redis_cache
from app.api.v2.auth_session_shared import get_user_data_from_session
from app.utils.rate_limiter import limiter
from app.services.localization import get_localization_service
from app.utils.auth_helpers import extract_user_role as _extract_user_role
from app.utils.timezone import now_sao_paulo

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
    db=Depends(get_db),
    redis_cache=Depends(get_redis_cache),
) -> Dict[str, Any]:
    """Simplified session validation for V2 endpoints."""
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session ID not provided in X-Session-ID header",
        )

    return await get_user_data_from_session(
        session_id=session_id,
        db=db,
        redis_cache=redis_cache,
    )


_ORIGINAL_GET_CURRENT_USER_SIMPLE = _get_current_user_simple
_ORIGINAL_GET_REDIS_CACHE = get_redis_cache


def _resolve_localization_attr(name: str, default: Any) -> Any:
    module = sys.modules.get("app.api.v2.routers.localization")
    if module is None:
        return default
    return getattr(module, name, default)


async def _resolve_awaitable_or_callable(value: Any, max_steps: int = 6) -> Any:
    """Resolve nested awaitable/callable objects produced by test patches."""
    current = value
    steps = 0
    while steps < max_steps:
        if inspect.isawaitable(current):
            current = await current
            steps += 1
            continue
        if callable(current):
            try:
                current = current()
            except TypeError:
                break
            steps += 1
            continue
        break
    return current


async def _get_redis_cache_compat():
    target = _resolve_localization_attr("get_redis_cache", _ORIGINAL_GET_REDIS_CACHE)
    if target is _ORIGINAL_GET_REDIS_CACHE:
        return await _ORIGINAL_GET_REDIS_CACHE()

    result = target() if callable(target) else target
    return await _resolve_awaitable_or_callable(result)


async def _get_current_user_simple_compat(
    session_id: str = Header(None, alias="X-Session-ID"),
    db=Depends(get_db),
    redis_cache=Depends(_get_redis_cache_compat),
) -> Dict[str, Any]:
    target = _resolve_localization_attr(
        "_get_current_user_simple", _ORIGINAL_GET_CURRENT_USER_SIMPLE
    )

    if target is _ORIGINAL_GET_CURRENT_USER_SIMPLE:
        return await _ORIGINAL_GET_CURRENT_USER_SIMPLE(
            session_id=session_id,
            db=db,
            redis_cache=redis_cache,
        )

    try:
        result = target(session_id=session_id, db=db, redis_cache=redis_cache)
    except TypeError:
        try:
            result = target(session_id=session_id)
        except TypeError:
            result = target()

    return await _resolve_awaitable_or_callable(result)


def _check_admin(current_user: Dict[str, Any]) -> None:
    """Ensure user is an admin."""
    role = _extract_user_role(current_user)
    if role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform this action",
        )


def _resolve_fallback_chain(language: str) -> List[str]:
    """Resolve fallback chain for a language (e.g., pt-BR → pt-PT → en-US)."""
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
    """Apply pluralization rules. Format: {singular|plural}."""
    # Simple pluralization: {singular|plural}
    pattern = r"\{([^{}|]+)\|([^{}]+)\}"

    def replace_plural(match):
        singular = match.group(1)
        plural = match.group(2)
        return singular if count == 1 else plural

    result = re.sub(pattern, replace_plural, text)

    # Replace {count} placeholder
    result = result.replace("{count}", str(count))

    return result


def _substitute_variables(text: str, variables: Optional[Dict[str, Any]] = None) -> str:
    """Substitute variables in text. Format: {variable_name}."""
    if not variables:
        return text

    try:
        pattern = r"\{([a-zA-Z0-9_]+)\}"

        def _replace(match):
            key = match.group(1)
            if key in variables:
                return str(variables[key])
            return match.group(0)

        return re.sub(pattern, _replace, text)
    except Exception as e:
        logger.error(f"Error substituting variables: {e}")
        return text


def _get_translation_with_fallback(
    key: str,
    language: str,
    namespace: str = "common",
    context: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    count: Optional[int] = None,
) -> str:
    """Get translation with fallback chain, pluralization, and variable substitution."""
    localization_service = get_localization_service()
    fallback_chain = _resolve_fallback_chain(language)

    for lang in fallback_chain:
        try:
            # Try to get translation from service
            text = localization_service.translate(
                key=key, locale=lang, namespace=namespace, fallback=None
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
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> LanguageV2List:
    """List supported languages with metadata. Cached for 24 hours."""
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
                "is_default": code == DEFAULT_LANGUAGE,
            }

            # Keep schema-required fields even when clients request subsets.
            if fields:
                selected = apply_field_selection(lang_data, fields)
                if isinstance(selected, dict):
                    lang_data.update(selected)

            languages.append(lang_data)

        result = LanguageV2List(
            data=languages, total=len(languages), default_language=DEFAULT_LANGUAGE
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_LANGUAGES)

        return result

    except Exception as e:
        logger.error(f"Error listing languages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve languages",
        )


@router.get("/translations/{language}", response_model=TranslationV2List)
@limiter.limit("100/minute")
async def get_translations_for_language(
    language: str,
    request: Request,
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    search: Optional[str] = Query(None, description="Search in keys or values"),
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> TranslationV2List:
    """Get all translations for language with namespace filtering and search. Cached for 4 hours."""
    try:
        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported",
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
                key: value
                for key, value in all_translations.items()
                if search_lower in key.lower()
                or (isinstance(value, str) and search_lower in value.lower())
            }

        # Build response
        translation_list = [
            {
                "key": key,
                "value": value,
                "namespace": key.split(".")[0] if "." in key else "common",
            }
            for key, value in all_translations.items()
        ]

        result = TranslationV2List(
            data=translation_list,
            language=language,
            total=len(translation_list),
            namespaces=namespaces_to_fetch,
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_TRANSLATIONS)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting translations for {language}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translations",
        )


def _flatten_translations(
    translations: Dict[str, Any], prefix: str = "", separator: str = "."
) -> Dict[str, str]:
    """Flatten nested translation dictionary to dot notation."""
    flat = {}

    for key, value in translations.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict):
            flat.update(_flatten_translations(value, new_key, separator))
        else:
            flat[new_key] = str(value)

    return flat


@router.get(
    "/translations/{language}/{key:path}", response_model=TranslationKeyV2Response
)
@limiter.limit("100/minute")
async def get_translation_by_key(
    language: str,
    key: str,
    request: Request,
    context: Optional[str] = Query(None, description="Context (formal/informal)"),
    variables: Optional[str] = Query(None, description="JSON-encoded variables"),
    count: Optional[int] = Query(None, description="Count for pluralization"),
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> Dict[str, Any]:
    """Get translation by key with fallback chain, context, variables, and pluralization."""
    try:
        if not key or not key.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Translation key cannot be empty",
            )

        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported",
            )

        # Parse variables if provided
        parsed_variables = None
        if variables:
            try:
                parsed_variables = json.loads(variables)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for variables",
                )

        # Extract namespace from key (first part before dot)
        namespace = key.split(".")[0] if "." in key else "common"
        if namespace not in NAMESPACES:
            namespace = "common"

        # Build cache key (without variables for better cache hit rate)
        cache_key = (
            f"i18n:key:{language}:{key}:ctx:{context or 'none'}:cnt:{count or 'none'}"
        )

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
            count=count,
        )

        # Determine which language was used (for transparency)
        fallback_chain = _resolve_fallback_chain(language)
        used_language = language  # Will be updated if fallback was used

        # Check if we used fallback
        localization_service = get_localization_service()
        for lang in fallback_chain:
            try:
                test_translation = localization_service.translate(
                    key=key, locale=lang, namespace=namespace, fallback=None
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
            "has_variables": parsed_variables is not None,
        }

        # Cache the result (only if no variables)
        if not parsed_variables:
            await redis_cache.set(cache_key, response, ttl=CACHE_TTL_TRANSLATIONS)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting translation {key} for {language}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve translation",
        )


@router.put(
    "/translations/{language}/{key:path}", response_model=TranslationKeyV2Response
)
@limiter.limit("30/minute")
async def update_translation(
    language: str,
    key: str,
    translation_data: TranslationV2Update,
    request: Request,
    db=Depends(get_db),
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> Dict[str, Any]:
    """Update translation (Admin only). Updates in-memory cache and invalidates Redis."""
    try:
        # Check admin permission
        _check_admin(current_user)

        # Validate language
        if language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Language '{language}' not supported",
            )

        # Extract namespace
        namespace = key.split(".")[0] if "." in key else "common"
        if namespace not in NAMESPACES:
            namespace = "common"

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
            "has_variables": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error updating translation {key} for {language}: {str(e)}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update translation",
        )


@router.get("/user/language", response_model=UserLanguagePreferenceV2)
@limiter.limit("100/minute")
async def get_user_language_preference(
    request: Request,
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> UserLanguagePreferenceV2:
    """Get user's language preference. Cached for 1 hour."""
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
            logger.warning(
                f"Invalid language preference '{language_pref}' for user {user_id}, using default"
            )
            language_pref = DEFAULT_LANGUAGE

        result = UserLanguagePreferenceV2(
            user_id=UUID(user_id),
            language=language_pref,
            is_default=language_pref == DEFAULT_LANGUAGE,
            updated_at=now_sao_paulo(),
        )

        # Cache the result
        await redis_cache.set(cache_key, result.dict(), ttl=CACHE_TTL_USER_PREFS)

        return result

    except Exception as e:
        logger.error(f"Error getting user language preference: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve language preference",
        )


@router.put("/user/language", response_model=UserLanguagePreferenceV2)
@limiter.limit("30/minute")
async def set_user_language_preference(
    preference_data: UserLanguagePreferenceV2Update,
    request: Request,
    redis_cache=Depends(_get_redis_cache_compat),
    current_user: Dict = Depends(_get_current_user_simple_compat),
) -> UserLanguagePreferenceV2:
    """Set user's language preference with validation and cache invalidation."""
    try:
        user_id = current_user.get("id")

        # Validate language
        if preference_data.language not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{preference_data.language}' not supported. "
                f"Supported languages: {', '.join(SUPPORTED_LANGUAGES.keys())}",
            )

        # Check if language is enabled
        if not SUPPORTED_LANGUAGES[preference_data.language].get("enabled", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Language '{preference_data.language}' is not enabled",
            )

        # Store preference in Redis
        user_pref_key = f"user:{user_id}:preferences:language"
        await redis_cache.set(
            user_pref_key, preference_data.language, ttl=None
        )  # No expiry

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
            updated_at=now_sao_paulo(),
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user language preference: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update language preference",
        )
