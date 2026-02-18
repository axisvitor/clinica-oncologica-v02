"""
Main template loader service.

Contains the EnhancedTemplateLoader class that provides DB-only template
loading with in-memory caching and versioning support.
"""

from typing import Dict, List, Optional, Any
from datetime import timedelta
import logging

from app.models.flow import FlowTemplateVersion
from app.repositories.flow_kind import FlowKindRepository
from app.repositories.flow_template_version import FlowTemplateVersionRepository
from app.utils.version_utils import (
    normalize_version,
    to_int_version,
    VersionError,
)
from app.utils.timezone import now_sao_paulo

from app.services.template_loader_pkg.models import (
    MessageType,
    MessageTemplate,
    FlowTemplateData,
)
from app.services.template_loader_pkg.exceptions import TemplateLoadError
from app.services.template_loader_pkg.validation import TemplateValidator

logger = logging.getLogger(__name__)


class EnhancedTemplateLoader:
    """
    DB-only template loader that uses the new versioning system.
    All templates MUST be in the database - no YAML fallback.
    """

    def __init__(self, db: Any, cache_ttl_hours: int = 1, max_cache_size: int = 50):
        self.db = db
        self.flow_kind_repo = FlowKindRepository(db)
        self.template_version_repo = FlowTemplateVersionRepository(db)
        self._template_cache: Dict[str, tuple[FlowTemplateData, Any]] = {}
        self._validator = TemplateValidator()
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        self._max_cache_size = max_cache_size
        logger.info("Initialized versioned template loader - DB-only mode")

    # -- Public: loading ------------------------------------------------

    def load_flow_template(
        self, flow_type: str, version: Optional[str] = None
    ) -> FlowTemplateData:
        cache_key = f"{flow_type}:{version or 'current'}"
        if cache_key in self._template_cache:
            cached_template, cached_time = self._template_cache[cache_key]
            if now_sao_paulo() - cached_time < self._cache_ttl:
                logger.debug(f"Loading template from cache: {cache_key}")
                return cached_template
            else:
                del self._template_cache[cache_key]
                logger.debug(f"Cache expired for template: {cache_key}")
        try:
            template_data = self._load_from_database(flow_type, version)
            if template_data:
                self._cache_template(cache_key, template_data)
                logger.info(
                    f"Successfully loaded template from DB: "
                    f"{flow_type} v{template_data.version}"
                )
                return template_data
            raise TemplateLoadError(f"Template {flow_type} not found in database")
        except Exception as e:
            logger.error(f"Failed to load template {flow_type}: {str(e)}")
            raise TemplateLoadError(
                f"Failed to load template {flow_type}: {str(e)}"
            )

    def get_message_for_day(
        self, flow_type: str, day: int, version: Optional[str] = None
    ) -> Optional[MessageTemplate]:
        try:
            template = self.load_flow_template(flow_type, version)
            return template.messages.get(day)
        except TemplateLoadError:
            logger.warning(f"Could not load template {flow_type} for day {day}")
            return None

    # -- Public: version info -------------------------------------------

    def get_current_version_info(self, flow_type: str) -> Optional[Dict[str, Any]]:
        try:
            kind_with_version = self.flow_kind_repo.get_with_current_version(flow_type)
            if kind_with_version:
                return {
                    "flow_type": kind_with_version.flow_type,
                    "kind_name": kind_with_version.kind_name,
                    "current_version": kind_with_version.version,
                    "status": kind_with_version.status,
                    "published_at": kind_with_version.published_at,
                    "duration_days": kind_with_version.duration_days,
                }
            return None
        except Exception as e:
            logger.error(f"Error getting current version info: {e}")
            return None

    def list_available_flow_types(self) -> List[Dict[str, Any]]:
        try:
            kinds_with_stats = self.flow_kind_repo.list_kinds_with_stats()
            return [
                {
                    "flow_type": kind.flow_type,
                    "name": kind.name,
                    "description": kind.description,
                    "total_versions": kind.total_versions,
                    "published_versions": kind.published_versions,
                    "draft_versions": kind.draft_versions,
                    "latest_version_date": kind.latest_version_date,
                    "has_current_version": hasattr(kind, "current_version_id_alias")
                    and kind.current_version_id_alias is not None,
                }
                for kind in kinds_with_stats
            ]
        except Exception as e:
            logger.error(f"Error listing flow types: {e}")
            return []

    def list_versions_for_flow_type(
        self, flow_type: str, status: str = None
    ) -> List[Dict[str, Any]]:
        try:
            kind = self.flow_kind_repo.get_by_kind_key(flow_type)
            if not kind:
                return []
            versions = self.template_version_repo.list_versions_by_kind(
                kind.id, status
            )
            return [
                {
                    "id": str(version.id),
                    "version": version.version,
                    "description": version.description,
                    "status": version.status,
                    "duration_days": version.duration_days,
                    "published_at": version.published_at,
                    "created_at": version.created_at,
                }
                for version in versions
            ]
        except Exception as e:
            logger.error(f"Error listing versions for flow type {flow_type}: {e}")
            return []

    # -- Public: version management -------------------------------------

    def create_template_version(
        self,
        flow_type: str,
        version: str,
        template_data: FlowTemplateData,
        description: str = None,
        created_by: str = None,
    ) -> bool:
        from app.utils.transaction_manager import sync_transaction

        try:
            with sync_transaction(self.db):
                kind = self.flow_kind_repo.get_by_kind_key(flow_type)
                if not kind:
                    kind = self.flow_kind_repo.create_kind(
                        flow_type=flow_type,
                        name=template_data.name,
                        description=description or template_data.description,
                    )
                self.template_version_repo.create_version(
                    kind_id=kind.id,
                    version=version,
                    template_data=template_data.to_dict(),
                    duration_days=len(template_data.messages),
                    description=description,
                    created_by=created_by,
                )
            self._invalidate_cache_for_flow_type(flow_type)
            logger.info(f"Created new template version: {flow_type} v{version}")
            return True
        except Exception as e:
            logger.error(f"Error creating template version: {e}")
            return False

    def publish_template_version(
        self, flow_type: str, version: str, set_as_current: bool = True
    ) -> bool:
        try:
            template_version = (
                self.template_version_repo.get_by_flow_type_and_version(
                    flow_type, version
                )
            )
            if not template_version:
                logger.error(f"Template version not found: {flow_type} v{version}")
                return False
            success = self.template_version_repo.publish_version(template_version.id)
            if not success:
                return False
            if set_as_current:
                kind = self.flow_kind_repo.get_by_kind_key(flow_type)
                if kind:
                    self.flow_kind_repo.update_current_version(
                        kind.id, template_version.id
                    )
            self._invalidate_cache_for_flow_type(flow_type)
            logger.info(f"Published template version: {flow_type} v{version}")
            return True
        except Exception as e:
            logger.error(f"Error publishing template version: {e}")
            return False

    # -- Internal: database loading -------------------------------------

    def _load_from_database(
        self, flow_type: str, version: Optional[str] = None
    ) -> Optional[FlowTemplateData]:
        try:
            version_num = None
            if version:
                try:
                    version_num = to_int_version(version)
                    logger.debug(
                        f"Normalized version '{version}' to integer {version_num}"
                    )
                except VersionError as ve:
                    logger.warning(f"Invalid version format '{version}': {ve}")
                    return None

            if version_num:
                template_version = (
                    self.template_version_repo.get_by_flow_type_and_version(
                        flow_type, version_num
                    )
                )
            else:
                template_version = (
                    self.template_version_repo.get_current_version_by_flow_type(
                        flow_type
                    )
                )
                if not template_version:
                    kind = self.flow_kind_repo.get_by_kind_key(flow_type)
                    if kind:
                        template_version = (
                            self.template_version_repo.get_latest_published_by_kind(
                                kind.id
                            )
                        )

            if not template_version:
                return None
            return self._parse_db_template_version(template_version)
        except Exception as e:
            logger.error(f"Error loading template from database: {e}")
            return None

    def _parse_db_template_version(
        self, version_model: FlowTemplateVersion
    ) -> FlowTemplateData:
        db_steps = version_model.steps or []
        message_templates: Dict[int, MessageTemplate] = {}

        if isinstance(db_steps, list):
            for step in db_steps:
                if not isinstance(step, dict):
                    continue
                day_num = step.get("day")
                if day_num is None:
                    continue
                try:
                    day_num = int(day_num)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Invalid day number in step: {step.get('day')}"
                    )
                    continue

                messages_list = step.get("messages", [])
                send_mode = step.get("send_mode", "single")

                base_content = ""
                if messages_list and isinstance(messages_list, list):
                    sorted_messages = sorted(
                        messages_list,
                        key=lambda m: (
                            m.get("order", 1) if isinstance(m, dict) else 1
                        ),
                    )
                    first_msg = sorted_messages[0] if sorted_messages else {}
                    base_content = (
                        first_msg.get("content", "")
                        if isinstance(first_msg, dict)
                        else str(first_msg)
                    )
                elif step.get("content"):
                    base_content = step.get("content", "")
                elif step.get("base_content"):
                    base_content = step.get("base_content", "")
                elif step.get("message"):
                    base_content = step.get("message", "")

                variations: list[str] = []
                normalized_send_mode = str(send_mode or "").strip().lower()
                sequential_modes = {
                    "sequential_auto",
                    "wait_each",
                    "wait_response",
                }
                if (
                    normalized_send_mode in sequential_modes
                    and len(messages_list) > 1
                ):
                    for msg in sorted(
                        messages_list,
                        key=lambda m: (
                            m.get("order", 1) if isinstance(m, dict) else 1
                        ),
                    )[1:]:
                        if isinstance(msg, dict) and msg.get("content"):
                            variations.append(msg.get("content"))

                message_templates[day_num] = MessageTemplate(
                    day=day_num,
                    intent=step.get("intent", f"day_{day_num}_message"),
                    base_content=base_content,
                    message_type=MessageType.TEXT,
                    core_elements=step.get("core_elements", {}),
                    personalization_hints=step.get(
                        "personalization_hints", ["patient_name"]
                    ),
                    ai_instructions=step.get("ai_instructions"),
                    variations=variations,
                )

        normalized_version = normalize_version(version_model.version_number)
        return FlowTemplateData(
            flow_type=(
                version_model.kind.kind_key if version_model.kind else "unknown"
            ),
            name=version_model.template_name,
            description=(
                version_model.description
                or f"Template version {normalized_version}"
            ),
            version=normalized_version,
            messages=message_templates,
            metadata=version_model.metadata_json or {},
        )

    # -- Internal: cache management -------------------------------------

    def _cache_template(
        self, cache_key: str, template_data: FlowTemplateData
    ) -> None:
        if len(self._template_cache) >= self._max_cache_size:
            oldest_key = min(
                self._template_cache.keys(),
                key=lambda k: self._template_cache[k][1],
            )
            del self._template_cache[oldest_key]
            logger.debug(f"Removed oldest cached template: {oldest_key}")
        self._template_cache[cache_key] = (template_data, now_sao_paulo())
        logger.debug(f"Cached template: {cache_key}")

    def _invalidate_cache_for_flow_type(self, flow_type: str) -> None:
        cache_keys_to_remove = [
            k for k in self._template_cache.keys() if k.startswith(flow_type)
        ]
        for key in cache_keys_to_remove:
            del self._template_cache[key]
        logger.debug(
            f"Invalidated {len(cache_keys_to_remove)} cache entries "
            f"for flow_type: {flow_type}"
        )

    def clear_cache(self) -> None:
        self._template_cache.clear()
        logger.info("Template cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        now = now_sao_paulo()
        expired_count = sum(
            1
            for _, cached_time in self._template_cache.values()
            if now - cached_time >= self._cache_ttl
        )
        return {
            "cache_size": len(self._template_cache),
            "max_cache_size": self._max_cache_size,
            "cache_utilization": len(self._template_cache) / self._max_cache_size,
            "expired_entries": expired_count,
            "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "database_enabled": True,
        }
