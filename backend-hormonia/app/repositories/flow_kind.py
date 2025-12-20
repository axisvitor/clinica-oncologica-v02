"""
Repository for Flow Kind management.
Standardized to match the RDS PostgreSQL schema.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.flow import FlowKind
from app.repositories.base import BaseRepository


class FlowKindRepository(BaseRepository):
    """Repository for FlowKind operations."""

    def __init__(self, db: Session):
        super().__init__(db, FlowKind)

    def get_by_kind_key(self, kind_key: str) -> Optional[FlowKind]:
        """Get flow kind by its unique key."""
        return self.db.query(FlowKind).filter(FlowKind.kind_key == kind_key).first()

    def list_active(self) -> List[FlowKind]:
        """List all active flow kinds."""
        return self.db.query(FlowKind).filter(FlowKind.is_active == True).all()

    def get_with_current_version(self, kind_key: str):
        """Get flow kind with its currently active version details."""
        query = text("""
            SELECT 
                fk.kind_key,
                fk.display_name,
                ftv.version_number,
                ftv.is_active,
                ftv.published_at,
                ftv.id as version_id
            FROM flow_kinds fk
            LEFT JOIN flow_template_versions ftv ON ftv.flow_kind_id = fk.id AND ftv.is_active = true
            WHERE fk.kind_key = :kind_key
            ORDER BY ftv.version_number DESC
            LIMIT 1
        """)
        return self.db.execute(query, {"kind_key": kind_key}).fetchone()

    def list_kinds_with_stats(self):
        """List all flow kinds with summary version statistics."""
        query = text("""
            SELECT 
                fk.kind_key,
                fk.display_name as name,
                fk.description,
                COUNT(ftv.id) as total_versions,
                COUNT(CASE WHEN ftv.is_active = true THEN 1 END) as published_versions,
                COUNT(CASE WHEN ftv.is_active = false THEN 1 END) as draft_versions,
                MAX(ftv.created_at) as latest_version_date,
                (
                    SELECT id 
                    FROM flow_template_versions 
                    WHERE flow_kind_id = fk.id AND is_active = true 
                    ORDER BY version_number DESC 
                    LIMIT 1
                ) as current_version_id
            FROM flow_kinds fk
            LEFT JOIN flow_template_versions ftv ON fk.id = ftv.flow_kind_id
            GROUP BY fk.id
            ORDER BY fk.kind_key
        """)
        return self.db.execute(query).fetchall()