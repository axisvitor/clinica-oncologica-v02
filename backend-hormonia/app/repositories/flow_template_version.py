"""
Repository for Flow Template Version management - handles versioned templates.

Database Schema (flow_template_versions):
- kind_id (UUID) - Foreign key to flow_kinds
- version (String) - Version identifier (e.g., "1.0.0")
- status (String) - draft, published, archived
- is_current (Boolean) - Whether this is the current active version
- messages (JSONB) - Flow message templates
- quiz_templates (JSONB) - Quiz/questionnaire templates
- alerts (JSONB) - Alert configurations
- changelog (Text) - Version change log
- created_by (UUID) - User who created this version
- approved_by (UUID) - User who approved/published this version
- published_at (DateTime) - When version was published
- archived_at (DateTime) - When version was archived
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from app.models.flow import FlowTemplateVersion
from app.repositories.base import BaseRepository


class FlowTemplateVersionRepository(BaseRepository):
    """Repository for FlowTemplateVersion operations."""

    def __init__(self, db: Session):
        super().__init__(db, FlowTemplateVersion)

    def get_by_kind_and_version(self, kind_id: UUID, version: str) -> Optional[FlowTemplateVersion]:
        """Get template version by kind and version."""
        return self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == kind_id,
            FlowTemplateVersion.version == version
        ).first()

    def get_latest_published_by_kind(self, kind_id: UUID) -> Optional[FlowTemplateVersion]:
        """Get the latest published version for a flow kind."""
        return self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == kind_id,
            FlowTemplateVersion.status == 'published'
        ).order_by(desc(FlowTemplateVersion.published_at)).first()

    def get_by_flow_type_and_version(self, flow_type: str, version: str = None) -> Optional[FlowTemplateVersion]:
        """Get template version by flow_type and version."""
        query = text("""
            SELECT ftv.*
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.kind_id = fk.id
            WHERE fk.flow_type = :flow_type
            AND (:version IS NULL OR ftv.version = :version)
            AND ftv.status = 'published'
            ORDER BY ftv.published_at DESC
            LIMIT 1
        """)

        result = self.db.execute(query, {
            "flow_type": flow_type,
            "version": version
        }).fetchone()

        if result:
            return self.db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == result.id
            ).first()
        return None

    def get_current_version_by_flow_type(self, flow_type: str) -> Optional[FlowTemplateVersion]:
        """Get the current version (marked as is_current=true) for a flow type."""
        result = self.db.execute(text("""
            SELECT ftv.*
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.kind_id = fk.id
            WHERE fk.flow_type = :flow_type
            AND ftv.is_current = true
        """), {"flow_type": flow_type}).fetchone()

        if result:
            return self.db.query(FlowTemplateVersion).filter(
                FlowTemplateVersion.id == result.id
            ).first()
        return None

    def list_versions_by_kind(self, kind_id: UUID, status: str = None) -> List[FlowTemplateVersion]:
        """List all versions for a flow kind, optionally filtered by status."""
        query = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.kind_id == kind_id
        )

        if status:
            query = query.filter(FlowTemplateVersion.status == status)

        return query.order_by(desc(FlowTemplateVersion.created_at)).all()

    def create_version(self, kind_id: UUID, version: str, messages: Dict[str, Any],
                      quiz_templates: Dict[str, Any] = None, alerts: Dict[str, Any] = None,
                      changelog: str = None, created_by: UUID = None) -> FlowTemplateVersion:
        """Create a new template version."""
        template_version = FlowTemplateVersion(
            kind_id=kind_id,
            version=version,
            messages=messages,
            quiz_templates=quiz_templates or {},
            alerts=alerts or {},
            changelog=changelog,
            status='draft',  # Always start as draft
            is_current=False,
            created_by=created_by
        )
        self.db.add(template_version)
        self.db.flush()  # Get the ID without committing
        return template_version

    def publish_version(self, version_id: UUID, published_by: UUID = None) -> bool:
        """Publish a draft version."""
        try:
            result = self.db.execute(
                text("""
                    UPDATE flow_template_versions
                    SET status = 'published',
                        published_at = NOW(),
                        approved_by = :approved_by,
                        updated_at = NOW()
                    WHERE id = :version_id AND status = 'draft'
                """),
                {"version_id": str(version_id), "approved_by": str(published_by) if published_by else None}
            )
            return result.rowcount > 0
        except Exception:
            return False

    def archive_version(self, version_id: UUID, archived_by: UUID = None) -> bool:
        """Archive a published version."""
        try:
            result = self.db.execute(
                text("""
                    UPDATE flow_template_versions
                    SET status = 'archived',
                        archived_at = NOW(),
                        updated_at = NOW()
                    WHERE id = :version_id AND status = 'published'
                """),
                {"version_id": str(version_id)}
            )
            return result.rowcount > 0
        except Exception:
            return False

    def update_messages(self, version_id: UUID, messages: Dict[str, Any],
                       quiz_templates: Dict[str, Any] = None,
                       alerts: Dict[str, Any] = None,
                       changelog: str = None) -> bool:
        """Update messages and other data for a draft version."""
        try:
            updates = {
                "messages": messages,
                "version_id": str(version_id)
            }

            query = """
                UPDATE flow_template_versions
                SET messages = :messages,
                    updated_at = NOW()
            """

            if quiz_templates is not None:
                query += ", quiz_templates = :quiz_templates"
                updates["quiz_templates"] = quiz_templates

            if alerts is not None:
                query += ", alerts = :alerts"
                updates["alerts"] = alerts

            if changelog is not None:
                query += ", changelog = :changelog"
                updates["changelog"] = changelog

            query += " WHERE id = :version_id AND status = 'draft'"

            result = self.db.execute(text(query), updates)
            return result.rowcount > 0
        except Exception:
            return False

    def get_message_for_day(self, flow_type: str, day: int, version: str = None) -> Optional[Dict[str, Any]]:
        """Get message template for a specific day from a flow template."""
        template_version = self.get_by_flow_type_and_version(flow_type, version)
        if not template_version:
            return None

        # Access messages directly - it's a JSONB column
        messages = template_version.messages or {}
        return messages.get(str(day))

    def search_templates(self, search_term: str = None, status: str = None,
                        flow_type: str = None) -> List[Dict[str, Any]]:
        """Search template versions with various filters."""
        query = text("""
            SELECT
                ftv.id,
                ftv.version,
                ftv.status,
                ftv.is_current,
                ftv.changelog,
                ftv.published_at,
                ftv.created_at,
                fk.flow_type,
                fk.name as kind_name
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.kind_id = fk.id
            WHERE 1=1
            AND (:search_term IS NULL OR fk.name ILIKE :search_pattern OR ftv.changelog ILIKE :search_pattern)
            AND (:status IS NULL OR ftv.status = :status)
            AND (:flow_type IS NULL OR fk.flow_type = :flow_type)
            ORDER BY fk.flow_type, ftv.created_at DESC
        """)

        search_pattern = f"%{search_term}%" if search_term else None

        return self.db.execute(query, {
            "search_term": search_term,
            "search_pattern": search_pattern,
            "status": status,
            "flow_type": flow_type
        }).fetchall()

    def get_version_analytics(self, version_id: UUID) -> Dict[str, Any]:
        """Get analytics for a specific template version."""
        # This would query usage statistics from patient_flow_states
        result = self.db.execute(text("""
            SELECT
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN pfs.current_step > 0 THEN 1 END) as active_sessions,
                COUNT(CASE WHEN pfs.completed_at IS NOT NULL THEN 1 END) as completed_sessions,
                AVG(pfs.current_step) as avg_progress
            FROM patient_flow_states pfs
            WHERE pfs.template_version_id = :version_id

            UNION ALL

            SELECT
                COUNT(*) as total_sessions,
                COUNT(CASE WHEN fs.current_step > 0 THEN 1 END) as active_sessions,
                COUNT(CASE WHEN fs.completed_at IS NOT NULL THEN 1 END) as completed_sessions,
                AVG(fs.current_step) as avg_progress
            FROM flow_states fs
            WHERE fs.template_version_id = :version_id
        """), {"version_id": str(version_id)}).fetchone()

        if result:
            return {
                "total_sessions": result.total_sessions or 0,
                "active_sessions": result.active_sessions or 0,
                "completed_sessions": result.completed_sessions or 0,
                "avg_progress": float(result.avg_progress or 0),
                "completion_rate": (result.completed_sessions / result.total_sessions * 100) if result.total_sessions > 0 else 0
            }

        return {
            "total_sessions": 0,
            "active_sessions": 0,
            "completed_sessions": 0,
            "avg_progress": 0,
            "completion_rate": 0
        }