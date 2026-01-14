"""
Repository for Flow Template Version management.
Standardized to match the RDS PostgreSQL schema (no status column).
"""

from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func

from app.models.flow import FlowTemplateVersion, PatientFlowState
from app.repositories.base import BaseRepository


class FlowTemplateVersionRepository(BaseRepository):
    """Repository for FlowTemplateVersion operations."""

    def __init__(self, db: Session):
        super().__init__(db, FlowTemplateVersion)

    def _parse_version_number(self, version: Any) -> int:
        if isinstance(version, int):
            return version
        if isinstance(version, str):
            try:
                return int(version)
            except ValueError:
                parts = version.split(".")
                for part in parts:
                    if part.isdigit():
                        return int(part)
        raise ValueError(f"Invalid version value: {version}")

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
            AND (:version_number IS NOT NULL OR ftv.is_active = true)
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
        self, flow_kind_id: UUID, status: Optional[str] = None
    ) -> List[FlowTemplateVersion]:
        """List all versions for a flow kind."""
        query = self.db.query(FlowTemplateVersion).filter(
            FlowTemplateVersion.flow_kind_id == flow_kind_id
        )

        if status:
            if status == "published":
                query = query.filter(
                    FlowTemplateVersion.is_draft.is_(False),
                    FlowTemplateVersion.is_active.is_(True),
                )
            elif status == "draft":
                query = query.filter(FlowTemplateVersion.is_draft.is_(True))
            elif status == "archived":
                query = query.filter(
                    FlowTemplateVersion.is_draft.is_(False),
                    FlowTemplateVersion.is_active.is_(False),
                )

        return query.order_by(desc(FlowTemplateVersion.created_at)).all()

    def create_version(
        self,
        flow_kind_id: UUID = None,
        kind_id: UUID = None,
        version_number: Optional[int] = None,
        version: Optional[Any] = None,
        steps: Optional[Any] = None,
        messages: Optional[Any] = None,
        template_data: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        description: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        quiz_templates: Optional[Dict[str, Any]] = None,
        alerts: Optional[Dict[str, Any]] = None,
        duration_days: Optional[int] = None,
        created_by: UUID = None,
        set_active: bool = False,
        is_draft: Optional[bool] = None,
        published_at: Optional[datetime] = None,
        **kwargs: Any,
    ) -> FlowTemplateVersion:
        """
        Create a new template version.
        Normalizes inputs from multiple call sites before saving.
        """
        resolved_kind_id = flow_kind_id or kind_id
        if not resolved_kind_id:
            raise ValueError("flow_kind_id is required")

        resolved_version = version_number if version_number is not None else version
        if resolved_version is None:
            raise ValueError("version_number is required")
        parsed_version = self._parse_version_number(resolved_version)

        resolved_steps = steps if steps is not None else messages
        if resolved_steps is None and template_data:
            if isinstance(template_data, dict):
                resolved_steps = (
                    template_data.get("steps")
                    or template_data.get("messages")
                    or template_data
                )

        resolved_template_name = template_name
        if not resolved_template_name and template_data and isinstance(template_data, dict):
            resolved_template_name = template_data.get("name") or template_data.get("template_name")
        if not resolved_template_name:
            resolved_template_name = f"Flow Template v{parsed_version}"

        resolved_metadata: Dict[str, Any] = {}
        if isinstance(metadata, dict):
            resolved_metadata.update(metadata)
        if template_data and isinstance(template_data, dict):
            resolved_metadata.update(template_data.get("metadata") or {})
        if quiz_templates:
            resolved_metadata["quiz_templates"] = quiz_templates
        if alerts:
            resolved_metadata["alerts"] = alerts
        if duration_days is not None:
            resolved_metadata["duration_days"] = duration_days

        resolved_is_draft = True if is_draft is None else is_draft
        resolved_published_at = published_at
        if not resolved_is_draft and resolved_published_at is None:
            resolved_published_at = datetime.now(timezone.utc)

        if set_active:
            # Deactivate all other versions for this kind first
            self.db.execute(
                text(
                    "UPDATE flow_template_versions SET is_active = false WHERE flow_kind_id = :kind_id"
                ),
                {"kind_id": resolved_kind_id},
            )

        template_version = FlowTemplateVersion(
            flow_kind_id=resolved_kind_id,
            version_number=parsed_version,
            template_name=resolved_template_name,
            steps=resolved_steps,
            description=description,
            is_active=set_active,
            is_draft=resolved_is_draft,
            published_at=resolved_published_at,
            metadata_json=resolved_metadata,
            created_by=created_by,
        )
        self.db.add(template_version)
        self.db.flush()
        return template_version

    def publish_version(
        self, version_id: UUID, published_by: Optional[UUID] = None, set_active: bool = False
    ) -> bool:
        """Publish a draft version."""
        try:
            version = self.get(version_id)
            if not version:
                return False

            version.is_draft = False
            version.published_at = version.published_at or datetime.now(timezone.utc)
            if set_active:
                self.db.execute(
                    text(
                        "UPDATE flow_template_versions SET is_active = false WHERE flow_kind_id = :kind_id"
                    ),
                    {"kind_id": version.flow_kind_id},
                )
                version.is_active = True

            if published_by:
                version.created_by = version.created_by or published_by

            self.db.flush()
            return True
        except Exception:
            self.db.rollback()
            return False

    def archive_version(self, version_id: UUID, archived_by: Optional[UUID] = None) -> bool:
        """Archive a published version."""
        try:
            version = self.get(version_id)
            if not version:
                return False
            version.is_active = False
            version.is_draft = False
            version.deprecated_at = datetime.now(timezone.utc)
            if archived_by:
                version.created_by = version.created_by or archived_by
            self.db.flush()
            return True
        except Exception:
            self.db.rollback()
            return False

    def get_version_analytics(self, version_id: UUID) -> Dict[str, Any]:
        """Return basic analytics for a template version."""
        total_flows = (
            self.db.query(func.count(PatientFlowState.id))
            .filter(PatientFlowState.flow_template_version_id == version_id)
            .scalar()
            or 0
        )
        active_flows = (
            self.db.query(func.count(PatientFlowState.id))
            .filter(
                PatientFlowState.flow_template_version_id == version_id,
                PatientFlowState.completed_at.is_(None),
            )
            .scalar()
            or 0
        )
        completed_flows = max(total_flows - active_flows, 0)
        completion_rate = (
            (completed_flows / total_flows) if total_flows > 0 else 0.0
        )

        avg_duration = (
            self.db.query(
                func.avg(
                    func.extract(
                        "epoch", PatientFlowState.completed_at - PatientFlowState.started_at
                    )
                )
            )
            .filter(
                PatientFlowState.flow_template_version_id == version_id,
                PatientFlowState.completed_at.is_not(None),
            )
            .scalar()
        )

        return {
            "total_flows": total_flows,
            "active_flows": active_flows,
            "completed_flows": completed_flows,
            "completion_rate": round(completion_rate, 4),
            "average_duration_seconds": avg_duration or 0.0,
        }

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
            version.is_draft = False
            version.published_at = version.published_at or datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
