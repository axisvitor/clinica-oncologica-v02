from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from app.models.flow import FlowTemplateVersion
from app.repositories.base import BaseRepository


class FlowTemplateRepository(BaseRepository[FlowTemplateVersion]):
    """Repository for FlowTemplateVersion model with eager loading optimization"""

    def __init__(self, db: Session):
        super().__init__(db, FlowTemplateVersion)

    def get_by_version(
        self, version: str, eager_load: bool = False
    ) -> Optional[FlowTemplateVersion]:
        """
        Get template by version with optional eager loading.

        Args:
            version: Template version string
            eager_load: Enable eager loading (default: False for single item)

        Returns:
            FlowTemplateVersion or None if not found
        """
        query = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.version == version
        )

        if eager_load:
            # Load kind relationship if needed
            query = query.options(joinedload(FlowTemplateVersion.kind))

        return query.first()

    def get_active_version(
        self, eager_load: bool = False
    ) -> Optional[FlowTemplateVersion]:
        """
        Get the current published template version with optional eager loading.

        Args:
            eager_load: Enable eager loading (default: False for single item)

        Returns:
            Current published FlowTemplateVersion or None
        """
        query = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.is_current, FlowTemplateVersion.status == "published"
        )

        if eager_load:
            query = query.options(joinedload(FlowTemplateVersion.kind))

        return query.order_by(FlowTemplateVersion.created_at.desc()).first()

    def get_all_versions(
        self, skip: int = 0, limit: int = 100, eager_load: bool = True
    ) -> List[FlowTemplateVersion]:
        """
        Get all template versions with eager loading.

        PERFORMANCE OPTIMIZATION: Eager loading enabled by default to prevent N+1 queries.

        Relationships loaded when eager_load=True:
        - kind: FlowKind information (joinedload - 1:1)

        Args:
            skip: Pagination offset
            limit: Maximum records to return
            eager_load: Enable eager loading (default: True for performance)

        Returns:
            List of flow template versions with relationships pre-loaded
        """
        query = self.db.query(FlowTemplateVersion)

        if eager_load:
            query = query.options(joinedload(FlowTemplateVersion.kind))

        return (
            query.order_by(FlowTemplateVersion.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
