"""
Flow template configuration loader.

Provides a light wrapper around ``flow_templates.yaml`` so domain modules
can query flow metadata without hard-coding YAML parsing logic. The loader:

* Parses the YAML once and keeps it cached in-memory
* Exposes helpers to fetch individual flow configurations
* Gives access to defaults, transitions, integrations, etc.
* Offers a simple ``reload`` method for future hot-reloads/tests
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

logger = logging.getLogger(__name__)


class FlowTemplateLoader:
    """Loads and serves data from ``flow_templates.yaml``."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """
        Args:
            config_path: Optional override path. Defaults to the YAML file
                that lives alongside this module.
        """
        default_path = Path(__file__).with_name("flow_templates.yaml")
        self.config_path = Path(config_path) if config_path else default_path
        self._config: Dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        """Reload the YAML file from disk."""
        self._load()

    def get_flow_config(self, flow_type: str) -> Optional[Dict[str, Any]]:
        """Return configuration dict for a given flow type."""
        flow_data = self._config.get("flow_types", {}).get(flow_type)
        if not flow_data:
            return None
        return copy.deepcopy(flow_data)

    def get_flow_types(self) -> Iterable[str]:
        """Yield the available flow type identifiers."""
        return self._config.get("flow_types", {}).keys()

    def get_defaults(self) -> Dict[str, Any]:
        """Return global defaults section."""
        return copy.deepcopy(self._config.get("defaults", {}))

    def get_transitions(self) -> Dict[str, Any]:
        """Return transition rules."""
        return copy.deepcopy(self._config.get("transitions", {}))

    def get_integrations(self) -> Dict[str, Any]:
        """Return integration settings."""
        return copy.deepcopy(self._config.get("integrations", {}))

    def get_monitoring(self) -> Dict[str, Any]:
        """Return monitoring configuration."""
        return copy.deepcopy(self._config.get("monitoring", {}))

    def get_feature_flags(self) -> Dict[str, Any]:
        """Return feature flag configuration."""
        return copy.deepcopy(self._config.get("feature_flags", {}))

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _load(self) -> None:
        """Parse the YAML file and cache the result."""
        try:
            with self.config_path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}
                if not isinstance(raw, dict):
                    raise ValueError("flow_templates.yaml must define a mapping at the root")

                self._config = raw
                logger.debug("FlowTemplateLoader loaded %s", self.config_path)
        except FileNotFoundError:
            logger.error("flow_templates.yaml not found at %s", self.config_path)
            self._config = {}
        except Exception as exc:
            logger.error("Error loading flow templates from %s: %s", self.config_path, exc)
            self._config = {}


__all__ = ["FlowTemplateLoader"]
