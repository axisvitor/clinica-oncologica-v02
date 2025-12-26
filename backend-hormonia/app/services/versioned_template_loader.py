"""
Versioned Template Loader Service
Manages loading and versioning of flow templates
"""

from typing import Dict, Optional, Any
from pathlib import Path
import json
import logging
from datetime import datetime, timezone

from app.utils.version_utils import (
    normalize_version,
    is_valid_version,
    compare_versions,
    DEFAULT_VERSION,
    VersionError,
)

logger = logging.getLogger(__name__)


class VersionedTemplateLoader:
    """Service for loading and managing versioned templates"""

    def __init__(self, template_path: Optional[Path] = None):
        """Initialize the template loader"""
        self.template_path = template_path or Path("app/templates")
        self.templates_cache: Dict[str, Any] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all templates from the template directory"""
        try:
            if self.template_path.exists():
                for template_file in self.template_path.glob("*.json"):
                    with open(template_file, "r", encoding="utf-8") as f:
                        template_data = json.load(f)
                        template_name = template_file.stem
                        self.templates_cache[template_name] = template_data
                        logger.info(f"Loaded template: {template_name}")
        except Exception as e:
            logger.error(f"Error loading templates: {e}")

    def get_template(
        self, template_name: str, version: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get a specific template by name and optional version

        Args:
            template_name: Name of the template
            version: Optional version string (semantic version or integer)

        Returns:
            Template data dictionary or None if not found
        """
        # Normalize version to semantic format
        if version:
            try:
                normalized_version = normalize_version(version)
            except VersionError:
                logger.warning(f"Invalid version format: {version}")
                normalized_version = version  # Keep original for backward compat
        else:
            normalized_version = None

        template_key = f"{template_name}_{normalized_version}" if normalized_version else template_name

        # Check cache first
        if template_key in self.templates_cache:
            return self.templates_cache[template_key]

        # Try to load from file if not in cache
        template_file = self.template_path / f"{template_key}.json"
        if template_file.exists():
            try:
                with open(template_file, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                    self.templates_cache[template_key] = template_data
                    return template_data
            except Exception as e:
                logger.error(f"Error loading template {template_key}: {e}")

        # Fallback to template without version
        if normalized_version and template_name in self.templates_cache:
            logger.debug(f"Falling back to non-versioned template: {template_name}")
            return self.templates_cache[template_name]

        return None

    def list_templates(self) -> Dict[str, Any]:
        """List all available templates with their metadata"""
        return {
            name: {
                "name": name,
                "version": normalize_version(data.get("version", DEFAULT_VERSION)),
                "description": data.get("description", ""),
                "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
            }
            for name, data in self.templates_cache.items()
        }

    def create_template(
        self, name: str, data: Dict, version: Optional[str] = None
    ) -> bool:
        """
        Create or update a template

        Args:
            name: Template name
            data: Template data
            version: Optional version string (semantic version or integer)

        Returns:
            True if successful
        """
        try:
            # Normalize version
            normalized_version = normalize_version(version) if version else DEFAULT_VERSION

            # Validate version format
            if not is_valid_version(normalized_version):
                logger.error(f"Invalid version format: {version}")
                return False

            template_key = f"{name}_{normalized_version}"

            # Add metadata with normalized version
            data["version"] = normalized_version
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            data["name"] = name

            # Save to file
            template_file = self.template_path / f"{template_key}.json"
            template_file.parent.mkdir(parents=True, exist_ok=True)

            with open(template_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            # Update cache
            self.templates_cache[template_key] = data
            logger.info(f"Created/updated template: {template_key}")
            return True

        except Exception as e:
            logger.error(f"Error creating template {name}: {e}")
            return False

    def delete_template(self, name: str, version: Optional[str] = None) -> bool:
        """
        Delete a template

        Args:
            name: Template name
            version: Optional version string (semantic version or integer)

        Returns:
            True if successful
        """
        try:
            # Normalize version if provided
            normalized_version = normalize_version(version) if version else None
            template_key = f"{name}_{normalized_version}" if normalized_version else name

            # Remove from cache
            if template_key in self.templates_cache:
                del self.templates_cache[template_key]

            # Remove file
            template_file = self.template_path / f"{template_key}.json"
            if template_file.exists():
                template_file.unlink()
                logger.info(f"Deleted template: {template_key}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting template {name}: {e}")
            return False

    def get_latest_version(self, template_name: str) -> Optional[str]:
        """
        Get the latest version of a template using semantic version comparison.

        Args:
            template_name: Name of the template

        Returns:
            Latest version string in semantic format, or None if no versions found
        """
        versions = []
        for key in self.templates_cache.keys():
            if key.startswith(template_name):
                if "_" in key:
                    version_str = key.split("_", 1)[1]
                    try:
                        # Normalize and validate version
                        normalized = normalize_version(version_str)
                        versions.append(normalized)
                    except VersionError:
                        logger.warning(f"Invalid version in cache key: {key}")
                        continue

        if versions:
            # Sort versions using semantic version comparison
            versions.sort(key=lambda v: tuple(map(int, v.split('.'))))
            latest = versions[-1]
            logger.debug(f"Latest version for {template_name}: {latest}")
            return latest

        return None


# Global instance
_template_loader: Optional[VersionedTemplateLoader] = None


def get_versioned_template_loader() -> VersionedTemplateLoader:
    """Get or create the global template loader instance"""
    global _template_loader
    if _template_loader is None:
        _template_loader = VersionedTemplateLoader()
    return _template_loader
