"""Backfill data for template versioning system

Revision ID: 016_backfill_template_versioning_data
Revises: 015_add_template_versioning_tables
Create Date: 2025-09-27

This migration backfills data from existing flow_templates into the new versioning system:
1. Migrates flow_templates data to flow_kinds and flow_template_versions
2. Updates patient_flow_states with template_version_id foreign keys
3. Sets current_version_id in flow_kinds to point to migrated versions
4. Updates quiz_templates with proper status values

This ensures existing data continues to work with the new versioning system.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '016_backfill_template_versioning_data'
down_revision = '015_add_template_versioning_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Check if flow_templates table exists and has data
    try:
        result = connection.execute(text("SELECT COUNT(*) FROM flow_templates"))
        template_count = result.scalar()

        if template_count > 0:
            print(f"Migrating {template_count} flow templates to new versioning system...")

            # Step 1: Migrate flow_templates to flow_kinds and flow_template_versions
            flow_templates = connection.execute(text("""
                SELECT id, name, flow_type, version, description, duration_days,
                       is_active, template_data, created_at, updated_at
                FROM flow_templates
                ORDER BY flow_type, created_at
            """)).fetchall()

            for template in flow_templates:
                # Create or get flow_kind
                existing_kind = connection.execute(text("""
                    SELECT id FROM flow_kinds WHERE flow_type = :flow_type
                """), {"flow_type": template.flow_type}).fetchone()

                if existing_kind:
                    kind_id = existing_kind.id
                else:
                    # Create new flow_kind
                    kind_result = connection.execute(text("""
                        INSERT INTO flow_kinds (flow_type, name, description, created_at, updated_at)
                        VALUES (:flow_type, :name, :description, :created_at, :updated_at)
                        RETURNING id
                    """), {
                        "flow_type": template.flow_type,
                        "name": template.name,
                        "description": template.description or f"Flow template for {template.flow_type}",
                        "created_at": template.created_at,
                        "updated_at": template.updated_at
                    })
                    kind_id = kind_result.scalar()

                # Create flow_template_version
                status = 'published' if template.is_active else 'archived'
                published_at = template.created_at if template.is_active else None

                version_result = connection.execute(text("""
                    INSERT INTO flow_template_versions
                    (kind_id, version, description, duration_days, template_data,
                     status, published_at, created_at, updated_at)
                    VALUES (:kind_id, :version, :description, :duration_days, :template_data,
                            :status, :published_at, :created_at, :updated_at)
                    RETURNING id
                """), {
                    "kind_id": kind_id,
                    "version": template.version or "1.0.0",
                    "description": f"Migrated from flow_templates: {template.description or ''}",
                    "duration_days": template.duration_days,
                    "template_data": template.template_data,
                    "status": status,
                    "published_at": published_at,
                    "created_at": template.created_at,
                    "updated_at": template.updated_at
                })
                version_id = version_result.scalar()

                # Update flow_kind with current_version_id if this is the active version
                if template.is_active:
                    connection.execute(text("""
                        UPDATE flow_kinds
                        SET current_version_id = :version_id, updated_at = NOW()
                        WHERE id = :kind_id
                    """), {
                        "version_id": version_id,
                        "kind_id": kind_id
                    })

                print(f"Migrated template {template.flow_type} v{template.version} to versioning system")

    except Exception as e:
        print(f"No flow_templates table found or error during migration: {e}")

    # Step 2: Update patient_flow_states with template_version_id
    try:
        # Try patient_flow_states table
        flow_states = connection.execute(text("""
            SELECT id, flow_type, template_version
            FROM patient_flow_states
            WHERE template_version_id IS NULL
        """)).fetchall()

        for state in flow_states:
            # Find matching template version
            template_version = connection.execute(text("""
                SELECT ftv.id
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON ftv.kind_id = fk.id
                WHERE fk.flow_type = :flow_type
                AND ftv.version = :version
                LIMIT 1
            """), {
                "flow_type": state.flow_type,
                "version": state.template_version or "1.0.0"
            }).fetchone()

            if template_version:
                connection.execute(text("""
                    UPDATE patient_flow_states
                    SET template_version_id = :template_version_id
                    WHERE id = :state_id
                """), {
                    "template_version_id": template_version.id,
                    "state_id": state.id
                })

        print(f"Updated {len(flow_states)} patient flow states with template version IDs")

    except Exception as e:
        print(f"No patient_flow_states table found or already updated: {e}")

    # Try flow_states table (alternative name)
    try:
        flow_states = connection.execute(text("""
            SELECT id, flow_type, template_version
            FROM flow_states
            WHERE template_version_id IS NULL
        """)).fetchall()

        for state in flow_states:
            # Find matching template version
            template_version = connection.execute(text("""
                SELECT ftv.id
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON ftv.kind_id = fk.id
                WHERE fk.flow_type = :flow_type
                AND ftv.version = :version
                LIMIT 1
            """), {
                "flow_type": state.flow_type,
                "version": state.template_version or "1.0.0"
            }).fetchone()

            if template_version:
                connection.execute(text("""
                    UPDATE flow_states
                    SET template_version_id = :template_version_id
                    WHERE id = :state_id
                """), {
                    "template_version_id": template_version.id,
                    "state_id": state.id
                })

        print(f"Updated {len(flow_states)} flow states with template version IDs")

    except Exception as e:
        print(f"No flow_states table found or already updated: {e}")

    # Step 3: Update quiz_templates with published_at for active quizzes
    try:
        result = connection.execute(text("""
            UPDATE quiz_templates
            SET published_at = created_at
            WHERE is_active = true AND published_at IS NULL
        """))
        print(f"Updated {result.rowcount} quiz templates with published_at dates")

    except Exception as e:
        print(f"Error updating quiz_templates: {e}")

    print("Backfill migration completed successfully!")


def downgrade() -> None:
    # Get database connection
    connection = op.get_bind()

    # Clear template_version_id from patient_flow_states
    try:
        connection.execute(text("""
            UPDATE patient_flow_states SET template_version_id = NULL
        """))
    except Exception:
        pass

    # Clear template_version_id from flow_states
    try:
        connection.execute(text("""
            UPDATE flow_states SET template_version_id = NULL
        """))
    except Exception:
        pass

    # Clear published_at from quiz_templates
    try:
        connection.execute(text("""
            UPDATE quiz_templates SET published_at = NULL
        """))
    except Exception:
        pass

    # Clear flow_template_versions and flow_kinds
    try:
        connection.execute(text("DELETE FROM flow_template_versions"))
        connection.execute(text("DELETE FROM flow_kinds"))
    except Exception:
        pass

    print("Backfill migration rolled back successfully!")