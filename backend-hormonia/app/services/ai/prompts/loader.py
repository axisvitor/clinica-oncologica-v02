"""
Prompt Template Loader
======================

Loads and renders YAML prompt templates with Jinja2 templating.
Provides caching and fallback for prompt management.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from jinja2 import Environment, BaseLoader, TemplateError

logger = logging.getLogger(__name__)

# Directory containing prompt templates
PROMPTS_DIR = Path(__file__).parent


class PromptLoader:
    """
    Loads and renders YAML prompt templates with Jinja2.
    
    Features:
    - YAML-based prompt storage
    - Jinja2 templating for dynamic content
    - Caching for performance
    - Fallback to hardcoded prompts on failure
    """

    def __init__(self, prompts_dir: Optional[Path] = None):
        """
        Initialize prompt loader.
        
        Args:
            prompts_dir: Directory containing YAML prompt files
        """
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._jinja_env = Environment(loader=BaseLoader())
        # Add tojson filter
        self._jinja_env.filters["tojson"] = lambda x: __import__("json").dumps(
            x, ensure_ascii=False, default=str
        )

    def _load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """Load and cache a YAML file."""
        if filename in self._cache:
            return self._cache[filename]

        filepath = self.prompts_dir / filename
        if not filepath.exists():
            logger.warning("Prompt file not found: %s", filepath)
            return {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self._cache[filename] = data
            logger.debug("Loaded prompt file: %s", filename)
            return data
        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML file %s: %s", filename, str(e))
            return {}
        except Exception as e:
            logger.error("Failed to load prompt file %s: %s", filename, str(e))
            return {}

    def get_prompt(
        self,
        prompt_name: str,
        filename: str = "healthcare_prompts.yaml",
        **variables: Any,
    ) -> Optional[str]:
        """
        Get and render a prompt template.
        
        Args:
            prompt_name: Name of the prompt (e.g., "humanization")
            filename: YAML file containing prompts
            **variables: Variables for template rendering
            
        Returns:
            Rendered prompt string or None if not found
        """
        data = self._load_yaml_file(filename)
        
        if prompt_name not in data:
            logger.warning("Prompt not found: %s in %s", prompt_name, filename)
            return None

        prompt_config = data[prompt_name]
        
        # Get user prompt (required)
        user_template = prompt_config.get("user", "")
        if not user_template:
            logger.warning("No user template for prompt: %s", prompt_name)
            return None

        try:
            template = self._jinja_env.from_string(user_template)
            rendered = template.render(**variables)
            return rendered.strip()
        except TemplateError as e:
            logger.error(
                "Template rendering failed for %s: %s",
                prompt_name,
                str(e),
                extra={"prompt_name": prompt_name, "variables": list(variables.keys())},
            )
            return None

    def get_system_prompt(
        self,
        prompt_name: str,
        filename: str = "healthcare_prompts.yaml",
    ) -> Optional[str]:
        """
        Get system prompt for a template.
        
        Args:
            prompt_name: Name of the prompt
            filename: YAML file containing prompts
            
        Returns:
            System prompt string or None
        """
        data = self._load_yaml_file(filename)
        
        if prompt_name not in data:
            return None

        return data[prompt_name].get("system")

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()
        logger.debug("Prompt cache cleared")


# Global prompt loader instance
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """Get global prompt loader singleton."""
    global _prompt_loader
    if _prompt_loader is None:
        _prompt_loader = PromptLoader()
    return _prompt_loader


@lru_cache(maxsize=32)
def get_cached_prompt(
    prompt_name: str,
    filename: str = "healthcare_prompts.yaml",
) -> Optional[str]:
    """
    Get raw prompt template (cached).
    
    For dynamic variables, use get_prompt_loader().get_prompt() instead.
    """
    loader = get_prompt_loader()
    data = loader._load_yaml_file(filename)
    if prompt_name not in data:
        return None
    return data[prompt_name].get("user")
