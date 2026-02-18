"""
Localization service for multi-language support in Hormonia Backend System.
Handles translation loading, caching, and text interpolation.
"""

import json
import logging
from typing import Any, Optional, List
from pathlib import Path
from functools import lru_cache

from app.config import settings


logger = logging.getLogger(__name__)


class LocalizationService:
    """
    Service for handling multi-language support.

    Provides translation loading, caching, and text interpolation
    for healthcare communication in multiple languages.
    """

    def __init__(self, default_locale: str = "en"):
        """
        Initialize localization service.

        Args:
            default_locale: Default language locale (e.g., 'en', 'pt-BR', 'es')
        """
        self.default_locale = default_locale
        self.locales_path = Path("app/locales")
        self._translations_cache: dict[str, dict[str, Any]] = {}
        self.supported_locales = self._discover_supported_locales()

        logger.info(
            f"Localization service initialized with default locale: {default_locale}"
        )
        logger.info(f"Supported locales: {self.supported_locales}")

    def _discover_supported_locales(self) -> List[str]:
        """Discover available locales from the locales directory."""
        if not self.locales_path.exists():
            logger.warning(f"Locales directory not found: {self.locales_path}")
            return [self.default_locale]

        locales = []
        for locale_dir in self.locales_path.iterdir():
            if locale_dir.is_dir():
                locales.append(locale_dir.name)

        return locales if locales else [self.default_locale]

    @lru_cache(maxsize=128)
    def _load_translation_file(self, locale: str, namespace: str) -> dict[str, Any]:
        """
        Load translation file for a specific locale and namespace.

        Args:
            locale: Language locale (e.g., 'en', 'pt-BR')
            namespace: Translation namespace (e.g., 'flows', 'messages')

        Returns:
            Dictionary containing translations
        """
        file_path = self.locales_path / locale / f"{namespace}.json"

        if not file_path.exists():
            logger.warning(f"Translation file not found: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                translations = json.load(f)

            logger.debug(f"Loaded translations for {locale}/{namespace}")
            return translations

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading translation file {file_path}: {e}")
            return {}

    def get_translations(self, locale: str, namespace: str) -> dict[str, Any]:
        """
        Get translations for a specific locale and namespace.

        Args:
            locale: Language locale
            namespace: Translation namespace

        Returns:
            Dictionary containing translations
        """
        cache_key = f"{locale}:{namespace}"

        if cache_key not in self._translations_cache:
            translations = self._load_translation_file(locale, namespace)
            self._translations_cache[cache_key] = translations

        return self._translations_cache[cache_key]

    def translate(
        self,
        key: str,
        locale: str = None,
        namespace: str = "flows",
        fallback: str = None,
        **kwargs,
    ) -> str:
        """
        Translate a key to the specified locale.

        Args:
            key: Translation key (dot-separated path, e.g., 'onboarding.steps.welcome.content')
            locale: Target locale (defaults to default_locale)
            namespace: Translation namespace
            fallback: Fallback text if translation not found
            **kwargs: Variables for text interpolation

        Returns:
            Translated text
        """
        if locale is None:
            locale = self.default_locale

        # Get translations for the locale
        translations = self.get_translations(locale, namespace)

        # Navigate through the nested dictionary using the key path
        try:
            value = translations
            for key_part in key.split("."):
                value = value[key_part]

            # Perform text interpolation if variables provided
            if kwargs and isinstance(value, str):
                value = value.format(**kwargs)

            return value

        except (KeyError, TypeError):
            # Try fallback to default locale if different
            if locale != self.default_locale:
                try:
                    default_translations = self.get_translations(
                        self.default_locale, namespace
                    )
                    value = default_translations
                    for key_part in key.split("."):
                        value = value[key_part]

                    if kwargs and isinstance(value, str):
                        value = value.format(**kwargs)

                    logger.warning(
                        f"Translation not found for {locale}, using default: {key}"
                    )
                    return value

                except (KeyError, TypeError) as e:
                    logger.debug(f"Failed to access nested translation key: {e}")

            # Use fallback or return the key itself
            result = fallback or key
            logger.warning(f"Translation not found: {locale}/{namespace}/{key}")
            return result

    def translate_flow_step(
        self, flow_type: str, step_name: str, field: str, locale: str = None, **kwargs
    ) -> str:
        """
        Translate a specific flow step field.

        Args:
            flow_type: Flow type (e.g., 'onboarding', 'quiz_mensal')
            step_name: Step name (e.g., 'welcome', 'daily_check_in')
            field: Field to translate (e.g., 'content', 'name')
            locale: Target locale
            **kwargs: Variables for text interpolation

        Returns:
            Translated text
        """
        key = f"{flow_type}.steps.{step_name}.{field}"
        return self.translate(key, locale, "flows", **kwargs)

    def translate_flow_metadata(
        self, flow_type: str, field: str, locale: str = None, **kwargs
    ) -> str:
        """
        Translate flow metadata (name, description).

        Args:
            flow_type: Flow type
            field: Metadata field ('name' or 'description')
            locale: Target locale
            **kwargs: Variables for text interpolation

        Returns:
            Translated text
        """
        key = f"{flow_type}.{field}"
        return self.translate(key, locale, "flows", **kwargs)

    def get_localized_flow_template(
        self, flow_template: dict[str, Any], locale: str = None
    ) -> dict[str, Any]:
        """
        Get a localized version of a flow template.

        Args:
            flow_template: Original flow template
            locale: Target locale

        Returns:
            Localized flow template
        """
        if locale is None:
            locale = self.default_locale

        localized_template = flow_template.copy()
        flow_type = flow_template.get("flow_type", "")

        # Translate metadata
        localized_template["name"] = self.translate_flow_metadata(
            flow_type, "name", locale
        )
        localized_template["description"] = self.translate_flow_metadata(
            flow_type, "description", locale
        )

        # Translate steps
        if "steps" in localized_template:
            for step in localized_template["steps"]:
                step_name = step.get("name", "")
                if "content" in step:
                    step["content"] = self.translate_flow_step(
                        flow_type, step_name, "content", locale
                    )

        return localized_template

    def clear_cache(self):
        """Clear the translations cache."""
        self._translations_cache.clear()
        self._load_translation_file.cache_clear()
        logger.info("Translation cache cleared")

    def reload_translations(self):
        """Reload all translations from disk."""
        self.clear_cache()
        self.supported_locales = self._discover_supported_locales()
        logger.info("Translations reloaded")


# Global localization service instance
_localization_service: Optional[LocalizationService] = None


def get_localization_service() -> LocalizationService:
    """Get global localization service instance."""
    global _localization_service

    if _localization_service is None:
        # Determine default locale from environment or configuration
        default_locale = getattr(settings, "DEFAULT_LOCALE", "en")
        _localization_service = LocalizationService(default_locale)

    return _localization_service


def translate(
    key: str,
    locale: str = None,
    namespace: str = "flows",
    fallback: str = None,
    **kwargs,
) -> str:
    """
    Convenience function for translation.

    Args:
        key: Translation key
        locale: Target locale
        namespace: Translation namespace
        fallback: Fallback text
        **kwargs: Variables for interpolation

    Returns:
        Translated text
    """
    service = get_localization_service()
    return service.translate(key, locale, namespace, fallback, **kwargs)
