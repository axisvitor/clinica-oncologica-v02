"""
Localization schemas for API v2

Enhanced i18n models with:
- Pydantic V2 validation and field constraints
- Comprehensive type hints and documentation
- Translation management models
- Language preference models
- Import/export schemas
- Search and statistics models

These schemas support the internationalization system with:
- Multiple languages (pt-BR, pt-PT, en-US, es-ES)
- Fallback chain support
- Context-aware translations
- Pluralization and variables
- User language preferences
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    ConfigDict,
    constr,
    conint,
    confloat,
)


# ============================================================================
# Enums and Constants
# ============================================================================


class LanguageCode(str, Enum):
    """Supported language codes."""

    PT_BR = "pt-BR"  # Portuguese (Brazil)
    PT_PT = "pt-PT"  # Portuguese (Portugal)
    EN_US = "en-US"  # English (United States)
    ES_ES = "es-ES"  # Spanish (Spain)


class TranslationNamespace(str, Enum):
    """Translation namespaces for organization."""

    FLOWS = "flows"
    MESSAGES = "messages"
    AUTH = "auth"
    COMMON = "common"
    ERRORS = "errors"
    EMAIL = "email"


class TranslationContext(str, Enum):
    """Context for context-aware translations."""

    FORMAL = "formal"
    INFORMAL = "informal"
    DEFAULT = "default"


class TextDirection(str, Enum):
    """Text direction for language rendering."""

    LTR = "ltr"  # Left-to-right
    RTL = "rtl"  # Right-to-left


# ============================================================================
# Language Schemas
# ============================================================================


class LanguageV2Response(BaseModel):
    """Language information response."""

    code: LanguageCode = Field(description="ISO language code (e.g., pt-BR, en-US)")
    name: constr(min_length=1, max_length=100) = Field(
        description="Language name in English"
    )
    native_name: constr(min_length=1, max_length=100) = Field(
        description="Language name in its native form"
    )
    direction: TextDirection = Field(
        default=TextDirection.LTR, description="Text direction (ltr or rtl)"
    )
    fallback: Optional[LanguageCode] = Field(
        None, description="Fallback language code if translation not found"
    )
    enabled: bool = Field(
        default=True, description="Whether this language is currently enabled"
    )
    is_default: bool = Field(
        default=False, description="Whether this is the default system language"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "pt-BR",
                "name": "Portuguese (Brazil)",
                "native_name": "Português (Brasil)",
                "direction": "ltr",
                "fallback": "pt-PT",
                "enabled": True,
                "is_default": False,
            }
        }
    )


class LanguageV2List(BaseModel):
    """List of available languages."""

    data: List[LanguageV2Response] = Field(description="List of supported languages")
    total: conint(ge=0) = Field(description="Total number of languages")
    default_language: LanguageCode = Field(description="Default system language")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "code": "pt-BR",
                        "name": "Portuguese (Brazil)",
                        "native_name": "Português (Brasil)",
                        "direction": "ltr",
                        "fallback": "pt-PT",
                        "enabled": True,
                        "is_default": False,
                    },
                    {
                        "code": "en-US",
                        "name": "English (United States)",
                        "native_name": "English (United States)",
                        "direction": "ltr",
                        "fallback": None,
                        "enabled": True,
                        "is_default": True,
                    },
                ],
                "total": 2,
                "default_language": "en-US",
            }
        }
    )


# ============================================================================
# Translation Schemas
# ============================================================================


class TranslationV2Response(BaseModel):
    """Single translation key-value pair."""

    key: constr(min_length=1, max_length=500) = Field(
        description="Translation key (dot-separated, e.g., auth.login.title)"
    )
    value: str = Field(description="Translated text")
    namespace: TranslationNamespace = Field(description="Translation namespace")

    @field_validator("key")
    @classmethod
    def validate_key_format(cls, v):
        """Ensure key follows dot notation."""
        if not v or not v.strip():
            raise ValueError("Key cannot be empty")
        # Allow letters, numbers, dots, underscores, hyphens
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError(
                "Key can only contain letters, numbers, dots, underscores, and hyphens"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "auth.login.title",
                "value": "Login to Your Account",
                "namespace": "auth",
            }
        }
    )


class TranslationV2List(BaseModel):
    """List of translations for a language."""

    data: List[Dict[str, Any]] = Field(
        description="List of translation key-value pairs"
    )
    language: LanguageCode = Field(description="Language code for these translations")
    total: conint(ge=0) = Field(description="Total number of translations")
    namespaces: List[str] = Field(
        default_factory=list, description="Namespaces included in this response"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "key": "auth.login.title",
                        "value": "Login to Your Account",
                        "namespace": "auth",
                    },
                    {
                        "key": "auth.login.button",
                        "value": "Sign In",
                        "namespace": "auth",
                    },
                ],
                "language": "en-US",
                "total": 2,
                "namespaces": ["auth"],
            }
        }
    )


class TranslationKeyV2Response(BaseModel):
    """Detailed response for a single translation key."""

    key: constr(min_length=1, max_length=500) = Field(description="Translation key")
    value: str = Field(description="Translated text (with variables substituted)")
    language: LanguageCode = Field(description="Requested language")
    used_language: LanguageCode = Field(
        description="Actual language used (may differ if fallback was used)"
    )
    fallback_used: bool = Field(description="Whether fallback language was used")
    namespace: TranslationNamespace = Field(description="Translation namespace")
    context: Optional[TranslationContext] = Field(
        None, description="Context used for translation (formal/informal)"
    )
    has_pluralization: bool = Field(
        default=False, description="Whether pluralization was applied"
    )
    has_variables: bool = Field(
        default=False, description="Whether variables were substituted"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "messages.sent",
                "value": "You have 5 messages",
                "language": "pt-BR",
                "used_language": "pt-BR",
                "fallback_used": False,
                "namespace": "messages",
                "context": None,
                "has_pluralization": True,
                "has_variables": True,
            }
        }
    )


class TranslationV2Update(BaseModel):
    """Schema for updating a translation."""

    value: constr(min_length=1, max_length=5000) = Field(
        description="New translation value"
    )

    @field_validator("value")
    @classmethod
    def validate_value(cls, v):
        """Ensure value is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Translation value cannot be empty or whitespace only")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={"example": {"value": "Login to Your Account"}}
    )


# ============================================================================
# User Language Preference Schemas
# ============================================================================


class UserLanguagePreferenceV2(BaseModel):
    """User's language preference."""

    user_id: UUID = Field(description="User UUID")
    language: LanguageCode = Field(description="Preferred language code")
    is_default: bool = Field(description="Whether this is the system default language")
    updated_at: datetime = Field(description="When preference was last updated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "language": "pt-BR",
                "is_default": False,
                "updated_at": "2025-01-17T15:00:00-03:00",
            }
        }
    )


class UserLanguagePreferenceV2Update(BaseModel):
    """Schema for updating user language preference."""

    language: str = Field(description="Language code to set as preference")

    model_config = ConfigDict(json_schema_extra={"example": {"language": "pt-BR"}})


# ============================================================================
# Import/Export Schemas
# ============================================================================


class TranslationExportV2(BaseModel):
    """Schema for exporting translations to JSON."""

    language: LanguageCode = Field(description="Language code to export")
    namespace: Optional[TranslationNamespace] = Field(
        None, description="Specific namespace to export (None = all)"
    )
    format: str = Field(default="json", description="Export format (json, csv, xliff)")
    include_metadata: bool = Field(
        default=True, description="Include metadata in export"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "language": "pt-BR",
                "namespace": "auth",
                "format": "json",
                "include_metadata": True,
            }
        }
    )


class TranslationImportV2(BaseModel):
    """Schema for importing translations from JSON."""

    language: LanguageCode = Field(description="Language code for import")
    namespace: TranslationNamespace = Field(
        description="Namespace for these translations"
    )
    translations: Dict[str, Any] = Field(
        description="Translation dictionary (nested or flat)"
    )
    overwrite_existing: bool = Field(
        default=False, description="Whether to overwrite existing translations"
    )

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, v):
        """Ensure translations dict is not empty."""
        if not v:
            raise ValueError("Translations dictionary cannot be empty")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "language": "pt-BR",
                "namespace": "auth",
                "translations": {
                    "login": {"title": "Entrar na Sua Conta", "button": "Entrar"}
                },
                "overwrite_existing": False,
            }
        }
    )


# ============================================================================
# Statistics and Search Schemas
# ============================================================================


class TranslationStatsV2(BaseModel):
    """Translation system statistics."""

    total_languages: conint(ge=0) = Field(
        description="Total number of supported languages"
    )
    enabled_languages: conint(ge=0) = Field(description="Number of enabled languages")
    total_keys: conint(ge=0) = Field(
        description="Total translation keys across all languages"
    )
    translations_by_language: Dict[str, int] = Field(
        description="Number of translations per language"
    )
    translations_by_namespace: Dict[str, int] = Field(
        description="Number of translations per namespace"
    )
    completion_percentage: Dict[str, float] = Field(
        description="Translation completion percentage per language"
    )
    last_updated: datetime = Field(description="When stats were last calculated")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_languages": 4,
                "enabled_languages": 4,
                "total_keys": 1250,
                "translations_by_language": {
                    "pt-BR": 1200,
                    "en-US": 1250,
                    "es-ES": 1100,
                    "pt-PT": 1150,
                },
                "translations_by_namespace": {
                    "auth": 45,
                    "messages": 230,
                    "flows": 560,
                    "common": 415,
                },
                "completion_percentage": {
                    "pt-BR": 96.0,
                    "en-US": 100.0,
                    "es-ES": 88.0,
                    "pt-PT": 92.0,
                },
                "last_updated": "2025-01-17T15:00:00-03:00",
            }
        }
    )


class MissingTranslationsV2(BaseModel):
    """Missing translations report."""

    language: LanguageCode = Field(description="Language being checked")
    reference_language: LanguageCode = Field(
        description="Reference language (usually default language)"
    )
    missing_keys: List[str] = Field(description="List of missing translation keys")
    total_missing: conint(ge=0) = Field(
        description="Total number of missing translations"
    )
    completion_percentage: confloat(ge=0, le=100) = Field(
        description="Percentage of translations completed"
    )
    by_namespace: Dict[str, int] = Field(
        description="Missing translations count by namespace"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "language": "es-ES",
                "reference_language": "en-US",
                "missing_keys": [
                    "auth.login.forgot_password",
                    "messages.notification_sent",
                ],
                "total_missing": 2,
                "completion_percentage": 98.4,
                "by_namespace": {"auth": 1, "messages": 1},
            }
        }
    )


class TranslationSearchV2(BaseModel):
    """Translation search request."""

    query: constr(min_length=1, max_length=200) = Field(
        description="Search query (searches both keys and values)"
    )
    languages: Optional[List[LanguageCode]] = Field(
        None, description="Limit search to specific languages (None = all)"
    )
    namespaces: Optional[List[TranslationNamespace]] = Field(
        None, description="Limit search to specific namespaces (None = all)"
    )
    case_sensitive: bool = Field(
        default=False, description="Whether search should be case-sensitive"
    )
    exact_match: bool = Field(
        default=False, description="Whether to match exactly (vs contains)"
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        """Ensure query is meaningful."""
        if not v or not v.strip():
            raise ValueError("Search query cannot be empty")
        if len(v.strip()) < 2:
            raise ValueError("Search query must be at least 2 characters")
        return v.strip()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "login",
                "languages": ["pt-BR", "en-US"],
                "namespaces": ["auth"],
                "case_sensitive": False,
                "exact_match": False,
            }
        }
    )


# ============================================================================
# Fallback Chain Schema
# ============================================================================


class FallbackChainV2(BaseModel):
    """Fallback chain for a language."""

    language: LanguageCode = Field(description="Source language")
    chain: List[LanguageCode] = Field(description="Fallback chain in order of priority")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"language": "pt-BR", "chain": ["pt-BR", "pt-PT", "en-US"]}
        }
    )


# ============================================================================
# Context-Aware Translation Schema
# ============================================================================


class ContextualTranslationV2(BaseModel):
    """Context-aware translation with multiple variants."""

    key: constr(min_length=1, max_length=500) = Field(description="Translation key")
    default: str = Field(description="Default translation")
    formal: Optional[str] = Field(None, description="Formal variant")
    informal: Optional[str] = Field(None, description="Informal variant")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "greeting.hello",
                "default": "Hello",
                "formal": "Good day",
                "informal": "Hey",
            }
        }
    )
