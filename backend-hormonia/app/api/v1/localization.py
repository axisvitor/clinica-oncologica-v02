"""
Localization API endpoints for testing and management.
"""
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.localization import get_localization_service
from app.services.template_loader import EnhancedTemplateLoader
from app.utils.localization import load_localized_flow_template, get_patient_locale


router = APIRouter()


@router.get("/supported-locales", response_model=None)
async def get_supported_locales() -> dict[str, List[str]]:
    """Get list of supported locales."""
    localization_service = get_localization_service()
    return {
        "supported_locales": localization_service.supported_locales,
        "default_locale": localization_service.default_locale
    }


@router.get("/translate", response_model=None)
async def translate_key(
    key: str = Query(..., description="Translation key (dot-separated)"),
    locale: str = Query("en", description="Target locale"),
    namespace: str = Query("flows", description="Translation namespace"),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Translate a specific key for testing purposes."""
    localization_service = get_localization_service()
    
    try:
        translated_text = localization_service.translate(
            key=key,
            locale=locale,
            namespace=namespace
        )
        
        return {
            "key": key,
            "locale": locale,
            "namespace": namespace,
            "translated_text": translated_text,
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Translation failed: {str(e)}"
        )


@router.get("/flow-template/{flow_type}", response_model=None)
async def get_localized_flow_template(
    flow_type: str,
    locale: str = Query("en", description="Target locale"),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get a localized flow template."""
    try:
        template_loader = EnhancedTemplateLoader()
        template = template_loader.load_template(flow_type, locale=locale)
        
        return {
            "flow_type": flow_type,
            "locale": locale,
            "template": {
                "name": template.name,
                "description": template.description,
                "duration_days": template.duration_days,
                "steps": [
                    {
                        "id": step.id,
                        "name": step.name,
                        "type": step.type,
                        "content": step.content,
                        "delay_hours": step.delay_hours
                    }
                    for step in template.steps
                ]
            },
            "success": True
        }
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Flow template not found: {flow_type}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load template: {str(e)}"
        )


@router.get("/patient-locale", response_model=None)
async def detect_patient_locale(
    phone: Optional[str] = Query(None, description="Patient phone number"),
    country: Optional[str] = Query(None, description="Patient country code"),
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Detect patient locale from metadata."""
    patient_metadata = {}
    
    if phone:
        patient_metadata["phone"] = phone
    if country:
        patient_metadata["country"] = country
    
    detected_locale = get_patient_locale(patient_metadata)
    
    return {
        "patient_metadata": patient_metadata,
        "detected_locale": detected_locale,
        "success": True
    }


@router.post("/reload-translations", response_model=None)
async def reload_translations(
    current_user: User = Depends(get_current_user)
) -> dict[str, str]:
    """Reload all translations from disk (development only)."""
    try:
        localization_service = get_localization_service()
        localization_service.reload_translations()
        
        return {
            "message": "Translations reloaded successfully",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload translations: {str(e)}"
        )


@router.get("/translation-stats", response_model=None)
async def get_translation_stats(
    current_user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Get translation system statistics."""
    localization_service = get_localization_service()
    
    stats = {
        "supported_locales": localization_service.supported_locales,
        "default_locale": localization_service.default_locale,
        "cache_size": len(localization_service._translations_cache),
        "available_namespaces": {}
    }
    
    # Count translations per locale and namespace
    for locale in localization_service.supported_locales:
        stats["available_namespaces"][locale] = {}
        
        for namespace in ["flows", "messages"]:
            try:
                translations = localization_service.get_translations(locale, namespace)
                stats["available_namespaces"][locale][namespace] = len(translations)
            except Exception:
                stats["available_namespaces"][locale][namespace] = 0
    
    return stats