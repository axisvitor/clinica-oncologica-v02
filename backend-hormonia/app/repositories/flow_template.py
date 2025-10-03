from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.flow import FlowTemplateVersion
from app.repositories.base import BaseRepository


class FlowTemplateRepository(BaseRepository[FlowTemplateVersion]):
    """Repository for FlowTemplateVersion model"""

    def __init__(self, db: Session):
        super().__init__(db, FlowTemplateVersion)

    def get_by_version(self, version: str) -> Optional[FlowTemplateVersion]:
        """Get template by version"""
        return (
            self.db.query(FlowTemplateVersion)
            .filter(FlowTemplateVersion.version == version)
            .first()
        )

    def get_active_version(self) -> Optional[FlowTemplateVersion]:
        """Get the current published template version"""
        return (
            self.db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.is_current == True,
                FlowTemplateVersion.status == 'published'
            )
            .order_by(FlowTemplateVersion.created_at.desc())
            .first()
        )

    def get_all_versions(self, skip: int = 0, limit: int = 100) -> List[FlowTemplateVersion]:
        """Get all template versions"""
        return (
            self.db.query(FlowTemplateVersion)
            .order_by(FlowTemplateVersion.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )