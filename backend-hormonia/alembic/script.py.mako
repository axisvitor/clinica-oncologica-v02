"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

WHY:
- [business reason]

WHAT:
- [schema/data changes]

IMPACT:
- [perf/data/lock impact]

BENCHMARK:
- [test results]

ROLLBACK:
- [safety/data loss]

RELATED:
- [issues/PRs/docs]

MIGRATION TYPE:
- [Schema-Only | Data Transformation | Zero-Downtime Multi-Step | Emergency]
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
