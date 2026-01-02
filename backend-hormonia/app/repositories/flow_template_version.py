"""
Repository for Flow Template Version management.
Standardized to match the RDS PostgreSQL schema (no status column).
"""

from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from app.models.flow import FlowTemplateVersion
from app.repositories.base import BaseRepository


class FlowTemplateVersionRepository(BaseRepository):
    """Repository for FlowTemplateVersion operations."""

    def __init__(self, db: Session):
        super().__init__(db, FlowTemplateVersion)

    def get_by_kind_and_version(
        self, flow_kind_id: UUID, version_number: int
    ) -> Optional[FlowTemplateVersion]:
        """Get template version by kind and version number."""
        return (
            self.db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.flow_kind_id == flow_kind_id,
                FlowTemplateVersion.version_number == version_number,
            )
            .first()
        )

    def get_latest_published_by_kind(
        self, flow_kind_id: UUID
    ) -> Optional[FlowTemplateVersion]:
        """Get the latest active version for a flow kind."""
        return (
            self.db.query(FlowTemplateVersion)
            .filter(
                FlowTemplateVersion.flow_kind_id == flow_kind_id,
                FlowTemplateVersion.is_active == True,
            )
            .order_by(desc(FlowTemplateVersion.version_number))
            .first()
        )

    def get_by_flow_type_and_version(
        self, kind_key: str, version_number: int = None
    ) -> Optional[FlowTemplateVersion]:
        """Get template version by kind_key and version_number."""
        query = text("""
            SELECT ftv.*
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
            WHERE fk.kind_key = :kind_key
            AND (:version_number IS NULL OR ftv.version_number = :version_number)
            AND ftv.is_active = true
            ORDER BY ftv.version_number DESC
            LIMIT 1
        """)

        result = self.db.execute(
            query, {"kind_key": kind_key, "version_number": version_number}
        ).fetchone()

        if result:
            return self.get(result.id)
        return None

    def get_current_version_by_flow_type(
        self, kind_key: str
    ) -> Optional[FlowTemplateVersion]:
        """Get the current version (marked as is_active=true) for a flow type."""
        query = text("""
            SELECT ftv.*
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
            WHERE fk.kind_key = :kind_key
            AND ftv.is_active = true
            ORDER BY ftv.version_number DESC
            LIMIT 1
        """)
        
        result = self.db.execute(query, {"kind_key": kind_key}).fetchone()

        if result:
            return self.get(result.id)
        return None

    def list_versions_by_kind(
        self, flow_kind_id: UUID, is_active: bool = None
    ) -> List[FlowTemplateVersion]:
        """List all versions for a flow kind."""
        query = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.flow_kind_id == flow_kind_id
        )

        if is_active is not None:
            query = query.filter(FlowTemplateVersion.is_active == is_active)

        return query.order_by(desc(FlowTemplateVersion.created_at)).all()

    def create_version(
        self,
        flow_kind_id: UUID,
        version_number: int,
        steps: Any,
        template_name: str,
        description: str = None,
        created_by: UUID = None,
        set_active: bool = False,
    ) -> FlowTemplateVersion:
        """
        Create a new template version.
        Normalizes steps to dictionary format before saving.
        """
        # Normalize steps to dict if it is a list
        normalized_steps = steps
        if isinstance(steps, list):
            normalized_steps = {}
            for idx, step in enumerate(steps):
                day = step.get("day") or step.get("step_number") or (idx + 1)
                normalized_steps[str(day)] = step

        if set_active:
            # Deactivate all other versions for this kind first
            self.db.execute(
                text("UPDATE flow_template_versions SET is_active = false WHERE flow_kind_id = :kind_id"),
                {"kind_id": flow_kind_id}
            )

        template_version = FlowTemplateVersion(
            flow_kind_id=flow_kind_id,
            version_number=version_number,
            template_name=template_name,
            steps=normalized_steps,
            description=description,
            is_active=set_active,
            created_by=created_by,
        )
        self.db.add(template_version)
        self.db.flush()
        return template_version

    def set_active_version(self, version_id: UUID) -> bool:
        """
        Set a specific version as the only active one for its kind.
        """
        try:
            # Get the version to find its kind_id
            version = self.get(version_id)
            if not version:
                return False
            
            # 1. Deactivate all versions for this kind
            self.db.execute(
                text("UPDATE flow_template_versions SET is_active = false WHERE flow_kind_id = :kind_id"),
                {"kind_id": version.flow_kind_id}
            )
            
            # 2. Activate only this one
            version.is_active = True
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
