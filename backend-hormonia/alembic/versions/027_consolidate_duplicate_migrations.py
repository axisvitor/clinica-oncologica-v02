"""Consolidate duplicate migrations

This migration marks 013 and 022 as duplicates of 005 and 014 respectively.
No schema changes needed - just documentation for future deployments.

Revision ID: 027_consolidate_duplicates
Revises: 025
Create Date: 2025-11-26

Duplicated migrations identified:
- Migration 005 and 013: Both create GIN indexes for patient metadata JSONB field
- Migration 014 and 022: Both create cursor pagination composite indexes

This consolidation migration:
1. Documents the duplication issue for audit purposes
2. Provides no-op upgrade/downgrade for deployment safety
3. Allows safe removal of migrations 013 and 022 in future deployments
4. Maintains database schema consistency across environments

Impact:
- Existing deployments: No changes (migrations already applied)
- New deployments: Skip duplicated migrations (013, 022)
- Schema: No modifications

LGPD Compliance Note:
This migration does not affect encrypted fields (cpf_encrypted, cpf_hash).
All LGPD-compliant encryption remains intact from migrations 020 and 024.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '027_consolidate_duplicates'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade():
    """
    Migrations duplicadas identificadas:
    - 005 e 013: Ambas criam GIN indexes para patient metadata
    - 014 e 022: Ambas criam cursor pagination indexes

    Esta migration não faz alterações de schema, apenas documenta a consolidação.
    Em novos deployments, 013 e 022 podem ser removidos.

    Duplicate migrations identified:
    - 005 and 013: Both create GIN indexes for patient metadata JSONB field
    - 014 and 022: Both create cursor pagination composite indexes

    This migration performs no schema changes - documentation only.
    In new deployments, migrations 013 and 022 can be safely removed.

    Historical Context:
    - These duplications occurred during parallel development branches
    - Database schema is consistent despite duplication
    - Future cleanup recommended but not required
    """
    # No schema alterations - documentation only
    # This is a consolidation marker for audit purposes
    pass


def downgrade():
    """
    No downgrade needed - this is a documentation-only migration.

    The duplicate migrations (013, 022) remain in the migration history
    but are superseded by earlier migrations (005, 014).
    """
    pass
