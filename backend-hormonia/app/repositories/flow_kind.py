"""
Repository for Flow Kind management.
Standardized to match the RDS PostgreSQL schema.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.flow import FlowKind
from app.repositories.base import BaseRepository


class FlowKindRepository(BaseRepository):
    """Repository for FlowKind operations."""

    FLOW_KIND_ALIASES = {
        "onboarding": ["initial_15_days"],
        "daily_follow_up": ["daily_checkin", "daily_engagement", "days_16_45"],
        "quiz_mensal": ["monthly_quiz", "monthly_recurring"],
        "custom": [],
    }

    def __init__(self, db: Session):
        super().__init__(db, FlowKind)

    def _resolve_kind_keys(self, kind_key: str) -> List[str]:
        if not kind_key:
            return []

        normalized = kind_key.strip()
        if normalized in self.FLOW_KIND_ALIASES:
            return [normalized] + self.FLOW_KIND_ALIASES[normalized]

        for canonical, aliases in self.FLOW_KIND_ALIASES.items():
            if normalized in aliases:
                return [normalized, canonical] + [
                    alias for alias in aliases if alias != normalized
                ]

        return [normalized]

    def get_by_kind_key(self, kind_key: str) -> Optional[FlowKind]:
        """Get flow kind by its unique key."""
        candidates = self._resolve_kind_keys(kind_key)
        if not candidates:
            return None
        return (
            self.db.query(FlowKind)
            .filter(FlowKind.kind_key.in_(candidates))
            .first()
        )

    def get_by_flow_type(self, flow_type: str) -> Optional[FlowKind]:
        """Alias for get_by_kind_key to preserve legacy service usage."""
        return self.get_by_kind_key(flow_type)

    def create_kind(
        self,
        flow_type: str,
        name: str,
        description: Optional[str] = None,
        is_active: bool = True,
    ) -> FlowKind:
        """Create a new flow kind entry."""
        kind = FlowKind(
            kind_key=flow_type,
            display_name=name,
            description=description,
            is_active=is_active,
        )
        self.db.add(kind)
        self.db.flush()
        return kind

    def update_current_version(self, kind_id: str, version_id: str) -> bool:
        """Set a specific version as active and deactivate others."""
        try:
            self.db.execute(
                text(
                    """
                    UPDATE flow_template_versions
                    SET is_active = false,
                        updated_at = now()
                    WHERE flow_kind_id = :kind_id
                    """
                ),
                {"kind_id": kind_id},
            )
            self.db.execute(
                text(
                    """
                    UPDATE flow_template_versions
                    SET is_active = true,
                        is_draft = false,
                        published_at = COALESCE(published_at, now()),
                        updated_at = now()
                    WHERE id = :version_id
                    """
                ),
                {"version_id": version_id},
            )
            self.db.flush()
            return True
        except Exception:
            self.db.rollback()
            return False

    def list_active(self) -> List[FlowKind]:
        """List all active flow kinds."""
        return self.db.query(FlowKind).filter(FlowKind.is_active == True).all()

    def get_all_active(self) -> List[FlowKind]:
        """Alias for list_active to match service expectations."""
        return self.list_active()

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
