"""
Flow template management service using the new versioning system.
"""
from typing import List, Optional, Any, Dict
from uuid import UUID

from app.models.flow import FlowKind, FlowTemplateVersion
from app.repositories.flow_kind import FlowKindRepository
from app.repositories.flow_template_version import FlowTemplateVersionRepository
from app.services.template_loader import EnhancedTemplateLoader, FlowTemplateData
from app.exceptions import ValidationError, NotFoundError


class FlowTemplateService:
    """Service for managing flow templates with versioning."""

    def __init__(self, db: Any):
        self.db = db
        self.flow_kind_repo = FlowKindRepository(db)
        self.template_version_repo = FlowTemplateVersionRepository(db)
        self.loader = EnhancedTemplateLoader(db=db)

    def get_current_template(self, flow_type: str) -> Optional[FlowTemplateData]:
        """
        Get the current published template for a flow type.

        Args:
            flow_type: The flow type identifier

        Returns:
            FlowTemplateData if found, None otherwise
        """
        try:
            return self.loader.load_flow_template(flow_type)
        except Exception:
            return None

    def get_template_by_version(self, flow_type: str, version: str) -> Optional[FlowTemplateData]:
        """
        Get a specific version of a template.

        Args:
            flow_type: The flow type identifier
            version: The version string

        Returns:
            FlowTemplateData if found, None otherwise
        """
        try:
            return self.loader.load_flow_template(flow_type, version)
        except Exception:
            return None

    def create_new_version(
        self,
        flow_type: str,
        version: str,
        messages: Dict[str, Any],
        quiz_templates: Optional[Dict[str, Any]] = None,
        alerts: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        created_by: Optional[UUID] = None
    ) -> FlowTemplateVersion:
        """
        Create a new template version for a flow type.

        Args:
            flow_type: The flow type identifier
            version: Version string for the new template
            messages: The messages data (day-based messages)
            quiz_templates: Optional quiz templates
            alerts: Optional alerts configuration
            description: Optional description
            created_by: Optional user ID who created this

        Returns:
            The created FlowTemplateVersion

        Raises:
            ValidationError: If version already exists or data is invalid
        """
        # Get or create flow kind
        flow_kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not flow_kind:
            flow_kind = self.flow_kind_repo.create_kind(
                flow_type=flow_type,
                name=messages.get('name', flow_type),
                description=description or messages.get('description')
            )
            self.db.flush()

        # Check if version already exists
        existing = self.template_version_repo.get_by_kind_and_version(flow_kind.id, version)
        if existing:
            raise ValidationError(f"Version {version} already exists for {flow_type}")

        # Create new version with new schema
        template_version = self.template_version_repo.create_version(
            kind_id=flow_kind.id,
            version=version,
            messages=messages,
            quiz_templates=quiz_templates or {},
            alerts=alerts or {},
            changelog=description,
            created_by=created_by
        )

        self.db.commit()
        return template_version

    def publish_version(
        self,
        flow_type: str,
        version: str,
        set_as_current: bool = True,
        published_by: Optional[UUID] = None
    ) -> bool:
        """
        Publish a draft template version.

        Args:
            flow_type: The flow type identifier
            version: Version to publish
            set_as_current: Whether to set this as the current version
            published_by: Optional user ID who published this

        Returns:
            True if successful, False otherwise
        """
        flow_kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not flow_kind:
            raise NotFoundError(f"Flow type {flow_type} not found")

        template_version = self.template_version_repo.get_by_kind_and_version(flow_kind.id, version)
        if not template_version:
            raise NotFoundError(f"Version {version} not found for {flow_type}")

        if template_version.status != 'draft':
            raise ValidationError(f"Only draft versions can be published. Current status: {template_version.status}")

        # Publish the version
        success = self.template_version_repo.publish_version(template_version.id, published_by)

        if success and set_as_current:
            self.flow_kind_repo.update_current_version(flow_kind.id, template_version.id)

        self.db.commit()
        return success

    def archive_version(
        self,
        flow_type: str,
        version: str,
        archived_by: Optional[UUID] = None
    ) -> bool:
        """
        Archive a published template version.

        Args:
            flow_type: The flow type identifier
            version: Version to archive
            archived_by: Optional user ID who archived this

        Returns:
            True if successful, False otherwise
        """
        flow_kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not flow_kind:
            raise NotFoundError(f"Flow type {flow_type} not found")

        template_version = self.template_version_repo.get_by_kind_and_version(flow_kind.id, version)
        if not template_version:
            raise NotFoundError(f"Version {version} not found for {flow_type}")

        if template_version.status != 'published':
            raise ValidationError(f"Only published versions can be archived. Current status: {template_version.status}")

        # Archive the version
        success = self.template_version_repo.archive_version(template_version.id, archived_by)

        self.db.commit()
        return success

    def list_flow_kinds(self) -> List[Dict[str, Any]]:
        """
        List all flow kinds with their statistics.

        Returns:
            List of flow kinds with version counts
        """
        kinds_with_stats = self.flow_kind_repo.list_kinds_with_stats()
        return [
            {
                "id": str(kind.id),
                "flow_type": kind.flow_type,
                "name": kind.name,
                "description": kind.description,
                "current_version_id": str(kind.current_version_id) if kind.current_version_id else None,
                "total_versions": kind.total_versions or 0,
                "published_versions": kind.published_versions or 0,
                "draft_versions": kind.draft_versions or 0,
                "latest_version_date": kind.latest_version_date
            }
            for kind in kinds_with_stats
        ]

    def list_versions(self, flow_type: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all versions for a flow type.

        Args:
            flow_type: The flow type identifier
            status: Optional filter by status

        Returns:
            List of template versions
        """
        flow_kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not flow_kind:
            return []

        versions = self.template_version_repo.list_versions_by_kind(flow_kind.id, status)
        return [
            {
                "id": str(version.id),
                "version": version.version,
                "description": version.description,
                "status": version.status,
                "duration_days": version.duration_days,
                "published_at": version.published_at,
                "created_at": version.created_at,
                "created_by": str(version.created_by) if version.created_by else None,
                "updated_by": str(version.updated_by) if version.updated_by else None
            }
            for version in versions
        ]

    def get_version_analytics(self, flow_type: str, version: str) -> Dict[str, Any]:
        """
        Get analytics for a specific template version.

        Args:
            flow_type: The flow type identifier
            version: The version string

        Returns:
            Analytics data for the version
        """
        flow_kind = self.flow_kind_repo.get_by_flow_type(flow_type)
        if not flow_kind:
            raise NotFoundError(f"Flow type {flow_type} not found")

        template_version = self.template_version_repo.get_by_kind_and_version(flow_kind.id, version)
        if not template_version:
            raise NotFoundError(f"Version {version} not found for {flow_type}")

        return self.template_version_repo.get_version_analytics(template_version.id)

    def get_template(self, flow_type: str, version: Optional[str] = None) -> Optional[FlowTemplateData]:
        """
        Get template data (compatibility method).

        Args:
            flow_type: The flow type identifier
            version: Optional version (defaults to current)

        Returns:
            FlowTemplateData if found
        """
        if version:
            return self.get_template_by_version(flow_type, version)
        else:
            return self.get_current_template(flow_type)

    def get_template_data(self, flow_type: str, version: Optional[str] = None) -> Optional[FlowTemplateData]:
        """
        Get template data using the EnhancedTemplateLoader.
        This method is required by FlowEngine.

        Args:
            flow_type: The flow type identifier
            version: Optional version (defaults to current)

        Returns:
            FlowTemplateData if found, None otherwise
        """
        try:
            return self.loader.load_flow_template(flow_type, version)
        except Exception as e:
            from app.services.template_loader import TemplateLoadError
            if isinstance(e, TemplateLoadError):
                # Template not found is expected, return None
                return None
            # Log unexpected errors
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading template {flow_type}: {e}")
            return None

    def get_all_templates(self, limit: Optional[int] = None) -> List[FlowTemplateData]:
        """
        Get all available flow templates.
        This method is required by FlowEngine for listing flows.

        Args:
            limit: Optional limit on number of templates to return

        Returns:
            List of FlowTemplateData objects for all available templates
        """
        try:
            # Get all flow types from the loader
            flow_types = self.loader.list_available_flow_types()

            templates = []
            for flow_type_info in flow_types:
                # Only include flow types that have a current version
                if not flow_type_info.get('has_current_version'):
                    continue

                try:
                    # Load the current template for each flow type
                    template = self.loader.load_flow_template(flow_type_info['flow_type'])
                    if template:
                        templates.append(template)

                        # Check if we've reached the limit
                        if limit and len(templates) >= limit:
                            break
                except Exception as e:
                    # Log error but continue with other templates
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not load template for {flow_type_info['flow_type']}: {e}")
                    continue

            return templates

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error getting all templates: {e}")
            return []
