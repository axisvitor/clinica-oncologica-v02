"""
API endpoints para gerenciamento de templates com hot-reload.
Permite reload manual, validação e monitoramento de cache.
"""
import logging
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from uuid import UUID

from app.database import get_db
from app.services.enhanced_flow_engine import get_enhanced_flow_engine, EnhancedFlowEngine

from app.services.flow_template import FlowTemplateService
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.flow import FlowTemplateResponse, FlowTemplateValidationResult
from app.exceptions import internal_server_exception, flow_operation_exception
from app.services.unified_cache import UnifiedCacheService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/reload", response_model=Dict[str, Any])
async def reload_templates(
    flow_type: Optional[str] = Query(None, description="Specific flow type to reload (all if not provided)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reload templates from database and invalidate cache.

    Forces reload of templates from database, invalidating Redis cache
    and triggering hot-reload across all instances.
    """
    try:
        flow_engine = get_enhanced_flow_engine(db)
        template_cache = get_template_cache(db)

        # Reload templates via flow engine
        reload_results = await flow_engine.reload_templates(flow_type)

        # Trigger hot-reload notification
        if flow_type:
            template_service = FlowTemplateService(db)
            template = template_service.get_template(flow_type)
            if template:
                await template_cache.publish_template_update(
                    flow_type=flow_type,
                    version=template.version,
                    operation="reloaded"
                )
        else:
            # Notify reload for all templates
            template_service = FlowTemplateService(db)
            templates = template_service.get_all_templates()
            for template in templates:
                await template_cache.publish_template_update(
                    flow_type=template.flow_type,
                    version=template.version,
                    operation="reloaded"
                )

        return {
            "success": True,
            "message": f"Templates reloaded successfully",
            "flow_type": flow_type or "all",
            "reload_results": reload_results,
            "reloaded_at": datetime.utcnow().isoformat(),
            "reloaded_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Failed to reload templates: {str(e)}")
        raise internal_server_exception("Failed to reload templates")


@router.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get template cache statistics and health status.

    Returns comprehensive cache statistics including Redis status,
    cached template counts, and hot-reload configuration.
    """
    try:
        template_cache = get_template_cache(db)
        flow_engine = get_enhanced_flow_engine(db)

        # Get cache stats
        cache_stats = await template_cache.get_cache_stats()

        # Get flow engine health
        engine_health = await flow_engine.health_check()

        return {
            "success": True,
            "cache_stats": cache_stats,
            "engine_health": engine_health,
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get cache stats: {str(e)}")
        raise internal_server_exception("Failed to get cache stats")


@router.post("/cache/warm", response_model=Dict[str, Any])
async def warm_template_cache(
    flow_types: Optional[List[str]] = Query(None, description="Specific flow types to warm"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Warm template cache by pre-loading templates.

    Pre-loads specified templates into Redis cache for better performance.
    If no flow types specified, warms all available templates.
    """
    try:
        template_cache = get_template_cache(db)

        # Warm cache
        warm_results = await template_cache.warm_cache(flow_types)

        return {
            "success": True,
            "message": "Cache warming completed",
            "warm_results": warm_results,
            "warmed_at": datetime.utcnow().isoformat(),
            "initiated_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Failed to warm cache: {str(e)}")
        raise internal_server_exception("Failed to warm cache")


@router.post("/validate", response_model=FlowTemplateValidationResult)
async def validate_template_structure(
    flow_type: str = Query(..., description="Flow type to validate"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> FlowTemplateValidationResult:
    """
    Validate template structure and content.

    Performs comprehensive validation of template structure,
    message content, AI optimization, and flow progression.
    """
    try:
        from app.services.template_loader import EnhancedTemplateLoader

        loader = EnhancedTemplateLoader(db=db)

        # Load template
        template_data = loader.load_flow_template(flow_type)
        if not template_data:
            raise HTTPException(
                status_code=404,
                detail=f"Template not found: {flow_type}"
            )

        # Validate template
        validation_result = loader.validate_template(template_data)

        return FlowTemplateValidationResult(
            is_valid=validation_result.is_valid,
            errors=validation_result.errors,
            warnings=validation_result.warnings,
            message_count=validation_result.message_count,
            ai_optimized_count=validation_result.ai_optimized_count,
            flow_type=flow_type,
            template_version=template_data.version,
            validated_at=datetime.utcnow().isoformat(),
            validated_by=current_user.email
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate template {flow_type}: {str(e)}")
        raise flow_operation_exception("template_validation", str(e))


@router.get("/preview/{flow_type}/{day}")
async def preview_message_template(
    flow_type: str,
    day: int,
    version: Optional[str] = Query(None, description="Template version"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Preview message template for specific day.

    Returns raw template content and metadata for preview purposes
    without generating personalized AI content.
    """
    try:
        template_cache = get_template_cache(db)

        # Get message template
        message_template = await template_cache.get_message_template(flow_type, day, version)
        if not message_template:
            raise HTTPException(
                status_code=404,
                detail=f"Message template not found for {flow_type} day {day}"
            )

        return {
            "success": True,
            "flow_type": flow_type,
            "day": day,
            "version": version,
            "template": {
                "intent": message_template.intent,
                "base_content": message_template.base_content,
                "message_type": message_template.message_type.value,
                "core_elements": message_template.core_elements,
                "personalization_hints": message_template.personalization_hints,
                "ai_instructions": message_template.ai_instructions,
                "variations": message_template.variations,
                "interactive_elements": message_template.interactive_elements.__dict__ if message_template.interactive_elements else None,
                "conditions": [
                    {
                        "type": c.type,
                        "field": c.field,
                        "operator": c.operator,
                        "value": c.value,
                        "logical_operator": c.logical_operator
                    } for c in message_template.conditions
                ],
                "follow_up": message_template.follow_up
            },
            "previewed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to preview template {flow_type} day {day}: {str(e)}")
        raise internal_server_exception("Failed to preview template")


@router.get("/health", response_model=Dict[str, Any])
async def check_template_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Comprehensive health check for template system.

    Tests database connectivity, Redis cache, template loading,
    and AI integration components.
    """
    try:
        flow_engine = get_enhanced_flow_engine(db)
        template_cache = get_template_cache(db)
        template_service = FlowTemplateService(db)

        # Flow engine health check
        engine_health = await flow_engine.health_check()

        # Cache stats
        cache_stats = await template_cache.get_cache_stats()

        # Template counts
        templates = template_service.get_all_templates()
        template_counts = {}
        for template in templates:
            template_counts[template.flow_type] = {
                "version": template.version,
                "message_count": len(template.template_data.get("messages", {})),
                "is_active": template.is_active
            }

        return {
            "success": True,
            "overall_healthy": engine_health.get("overall_healthy", False),
            "components": {
                "flow_engine": engine_health,
                "template_cache": cache_stats,
                "template_counts": template_counts
            },
            "checked_at": datetime.utcnow().isoformat(),
            "checked_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Failed template system health check: {str(e)}")
        raise internal_server_exception("Failed template system health check")


@router.post("/sync-from-files")
async def sync_templates_from_files(
    force: bool = Query(False, description="Force sync even if versions match"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Synchronize database templates with YAML files.

    Loads templates from YAML files and updates database,
    useful for development or initial setup.
    """
    try:
        template_service = FlowTemplateService(db)

        # Sync templates from files
        sync_results = template_service.sync_templates_from_files()

        # Invalidate cache for synced templates
        template_cache = get_template_cache(db)
        for flow_type, status in sync_results.items():
            if status in ["created", "updated"]:
                await template_cache.invalidate_template_cache(flow_type)

                # Publish update notification
                template = template_service.get_template(flow_type)
                if template:
                    await template_cache.publish_template_update(
                        flow_type=flow_type,
                        version=template.version,
                        operation="synced_from_file"
                    )

        return {
            "success": True,
            "message": "Templates synchronized from files",
            "sync_results": sync_results,
            "synced_at": datetime.utcnow().isoformat(),
            "synced_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Failed to sync templates from files: {str(e)}")
        raise internal_server_exception("Failed to sync templates from files")