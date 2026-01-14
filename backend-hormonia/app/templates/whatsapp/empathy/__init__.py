"""
Empathy message templates for WhatsApp follow-ups.
"""

from pathlib import Path
import random
from typing import Optional

_TEMPLATE_CACHE: dict[str, list[str]] = {}
_TEMPLATE_DIR = Path(__file__).parent


def _load_templates(category: str) -> list[str]:
    if category in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[category]

    templates: list[str] = []
    for path in sorted(_TEMPLATE_DIR.glob(f"{category}_*.txt")):
        content = path.read_text(encoding="utf-8").strip()
        if content:
            templates.append(content)

    _TEMPLATE_CACHE[category] = templates
    return templates


def get_empathy_template(category: str, patient_name: Optional[str] = None) -> str:
    """Return a formatted empathy template for a category."""
    templates = _load_templates(category)
    if not templates:
        return ""
    template = random.choice(templates)
    safe_name = patient_name or "voce"
    return template.format(patient_name=safe_name)
