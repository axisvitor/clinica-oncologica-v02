"""
Localization utilities for flow templates and message content.
"""
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

from app.services.localization import get_localization_service


def load_localized_flow_template(
    flow_file: str,
    locale: str = None
) -> Dict[str, Any]:
    """
    Load a flow template and return its localized version.
    
    Args:
        flow_file: Path to the flow template file
        locale: Target locale for localization
        
    Returns:
        Localized flow template
    """
    # Load the original template
    template_path = Path(flow_file)
    if not template_path.exists():
        raise FileNotFoundError(f"Flow template not found: {flow_file}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template = yaml.safe_load(f)
    
    # Get localized version
    localization_service = get_localization_service()
    return localization_service.get_localized_flow_template(template, locale)


def get_patient_locale(patient_metadata: Dict[str, Any]) -> str:
    """
    Determine patient's preferred locale from metadata.
    
    Args:
        patient_metadata: Patient metadata dictionary
        
    Returns:
        Patient's preferred locale or default locale
    """
    # Check for explicit locale preference
    if 'locale' in patient_metadata:
        return patient_metadata['locale']
    
    # Infer from country or phone number
    phone = patient_metadata.get('phone', '')
    if phone.startswith('55'):  # Brazil
        return 'pt-BR'
    elif phone.startswith('34') or phone.startswith('52'):  # Spain or Mexico
        return 'es'
    
    # Default to system default
    localization_service = get_localization_service()
    return localization_service.default_locale


def localize_message_content(
    content: str,
    locale: str = None,
    context: Dict[str, Any] = None
) -> str:
    """
    Localize message content with context variables.
    
    Args:
        content: Message content (may contain translation keys)
        locale: Target locale
        context: Context variables for interpolation
        
    Returns:
        Localized message content
    """
    if context is None:
        context = {}
    
    localization_service = get_localization_service()
    
    # If content looks like a translation key, translate it
    if '.' in content and not ' ' in content:
        return localization_service.translate(
            content, locale, "messages", content, **context
        )
    
    # Otherwise, return as-is (already localized content)
    return content.format(**context) if context else content