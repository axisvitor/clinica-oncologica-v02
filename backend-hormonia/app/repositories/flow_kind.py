"""
Repository for Flow Kind management - handles flow types and their metadata.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.flow import FlowKind  # We'll need to create this model
from app.repositories.base import BaseRepository


class FlowKindRepository(BaseRepository):
    """Repository for FlowKind operations."""

    def __init__(self, db: Session):
        super().__init__(db, FlowKind)

    def get_by_flow_type(self, flow_type: str) -> Optional[FlowKind]:
        """Get flow kind by flow_type."""
        return self.db.query(FlowKind).filter(FlowKind.flow_type == flow_type).first()

    def get_all_active(self) -> List[FlowKind]:
        """Get all flow kinds that have a current version."""
        # Use ORM query instead of raw SQL to avoid mapping issues
        from sqlalchemy import exists, select
        from app.models.flow import FlowTemplateVersion

        subquery = exists().where(
            FlowTemplateVersion.kind_id == FlowKind.id,
            FlowTemplateVersion.is_current == True
        )

        return self.db.query(FlowKind).filter(subquery).order_by(FlowKind.flow_type).all()

    def create_kind(self, flow_type: str, name: str, description: str = None) -> FlowKind:
        """Create a new flow kind."""
        kind = FlowKind(
            flow_type=flow_type,
            name=name,
            description=description
        )
        self.db.add(kind)
        self.db.flush()  # Get the ID without committing
        return kind

    def update_current_version(self, kind_id: UUID, version_id: UUID) -> bool:
        """Update the current version for a flow kind by setting is_current flag."""
        try:
            # First, unset is_current for all versions of this kind
            self.db.execute(
                text("UPDATE flow_template_versions SET is_current = false WHERE kind_id = :kind_id"),
                {"kind_id": str(kind_id)}
            )
            # Then set is_current for the specified version
            result = self.db.execute(
                text("UPDATE flow_template_versions SET is_current = true WHERE id = :version_id AND kind_id = :kind_id"),
                {"version_id": str(version_id), "kind_id": str(kind_id)}
            )
            return result.rowcount > 0
        except Exception:
            return False

    def get_with_current_version(self, flow_type: str):
        """Get flow kind with its current version details."""
        return self.db.execute(text("""
            SELECT
                fk.id as kind_id,
                fk.flow_type,
                fk.name as kind_name,
                fk.description as kind_description,
                fk.category,
                fk.is_active,
                fk.display_order,
                fk.metadata as flow_metadata,
                ftv.id as version_id,
                ftv.version,
                ftv.status,
                ftv.messages,
                ftv.quiz_templates,
                ftv.alerts,
                ftv.published_at
            FROM flow_kinds fk
            LEFT JOIN flow_template_versions ftv ON ftv.kind_id = fk.id AND ftv.is_current = true
            WHERE fk.flow_type = :flow_type
        """), {"flow_type": flow_type}).fetchone()

    def list_kinds_with_stats(self):
        """List all flow kinds with version statistics."""
        return self.db.execute(text("""
            SELECT
                fk.id,
                fk.flow_type,
                fk.name,
                fk.description,
                ftv_current.id as current_version_id_alias,  -- For compatibility, but use is_current instead
                COUNT(ftv.id) as total_versions,
                COUNT(CASE WHEN ftv.status = 'published' THEN 1 END) as published_versions,
                COUNT(CASE WHEN ftv.status = 'draft' THEN 1 END) as draft_versions,
                MAX(ftv.created_at) as latest_version_date
            FROM flow_kinds fk
            LEFT JOIN flow_template_versions ftv ON fk.id = ftv.kind_id
            LEFT JOIN flow_template_versions ftv_current ON fk.id = ftv_current.kind_id AND ftv_current.is_current = true
            GROUP BY fk.id, fk.flow_type, fk.name, fk.description, ftv_current.id
            ORDER BY fk.flow_type
        """)).fetchall()