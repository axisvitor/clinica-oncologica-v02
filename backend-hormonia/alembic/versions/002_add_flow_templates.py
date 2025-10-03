"""Add FlowTemplate model

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_flow_templates'
down_revision = '002_quiz_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create flow_templates table
    op.create_table('flow_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('flow_type', sa.String(50), nullable=False, unique=True),
        sa.Column('version', sa.String(20), nullable=False, server_default='1.0.0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('template_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )
    
    # Add template_version column to flow_states table
    op.add_column('flow_states', sa.Column('template_version', sa.String(20), nullable=False, server_default='1.0.0'))
    
    # Create indexes
    op.create_index('idx_flow_templates_flow_type', 'flow_templates', ['flow_type'])
    op.create_index('idx_flow_templates_is_active', 'flow_templates', ['is_active'])
    op.create_index('idx_flow_templates_version', 'flow_templates', ['version'])
    op.create_index('idx_flow_states_template_version', 'flow_states', ['template_version'])
    
    # Create trigger for updated_at column
    op.execute("CREATE TRIGGER update_flow_templates_updated_at BEFORE UPDATE ON flow_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")


def downgrade() -> None:
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_flow_templates_updated_at ON flow_templates")
    
    # Drop indexes
    op.drop_index('idx_flow_states_template_version', 'flow_states')
    op.drop_index('idx_flow_templates_version', 'flow_templates')
    op.drop_index('idx_flow_templates_is_active', 'flow_templates')
    op.drop_index('idx_flow_templates_flow_type', 'flow_templates')
    
    # Remove template_version column from flow_states
    op.drop_column('flow_states', 'template_version')
    
    # Drop flow_templates table
    op.drop_table('flow_templates')