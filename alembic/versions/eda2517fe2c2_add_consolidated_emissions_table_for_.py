"""Add consolidated emissions table for consolidation service

Revision ID: eda2517fe2c2
Revises: 10652023a6b7
Create Date: 2025-10-05 16:34:36.406828

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eda2517fe2c2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create consolidated_emissions table
    op.create_table('consolidated_emissions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('reporting_year', sa.Integer(), nullable=False),
        sa.Column('reporting_period_start', sa.Date(), nullable=False),
        sa.Column('reporting_period_end', sa.Date(), nullable=False),
        sa.Column('consolidation_method', sa.String(50), nullable=False),
        sa.Column('consolidation_date', sa.DateTime(), nullable=False),
        sa.Column('consolidation_version', sa.Integer(), nullable=False),
        sa.Column('total_scope1_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_scope2_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_scope3_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_co2', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_ch4_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_n2o_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_other_ghg_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_entities_included', sa.Integer(), nullable=False),
        sa.Column('entities_with_scope1', sa.Integer(), nullable=False),
        sa.Column('entities_with_scope2', sa.Integer(), nullable=False),
        sa.Column('entities_with_scope3', sa.Integer(), nullable=False),
        sa.Column('data_completeness_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('consolidation_confidence_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('entity_contributions', sa.Text(), nullable=True),  # JSON field
        sa.Column('consolidation_adjustments', sa.Text(), nullable=True),  # JSON field
        sa.Column('exclusions', sa.Text(), nullable=True),  # JSON field
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('is_final', sa.Boolean(), nullable=False),
        sa.Column('validation_status', sa.String(50), nullable=True),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_consolidated_company_year', 'consolidated_emissions', ['company_id', 'reporting_year'])
    op.create_index('idx_consolidated_status', 'consolidated_emissions', ['status'])
    op.create_index('idx_consolidated_date', 'consolidated_emissions', ['consolidation_date'])
    
    # Create consolidation audit trail table
    op.create_table('consolidation_audit_trail',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('consolidation_id', sa.String(36), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=True),
        sa.Column('event_description', sa.Text(), nullable=True),
        sa.Column('before_values', sa.Text(), nullable=True),  # JSON field
        sa.Column('after_values', sa.Text(), nullable=True),  # JSON field
        sa.Column('affected_entities', sa.Text(), nullable=True),  # JSON field
        sa.Column('system_info', sa.Text(), nullable=True),  # JSON field
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for audit trail
    op.create_index('idx_consolidation_audit_consolidation', 'consolidation_audit_trail', ['consolidation_id'])
    op.create_index('idx_consolidation_audit_timestamp', 'consolidation_audit_trail', ['event_timestamp'])
    op.create_index('idx_consolidation_audit_type', 'consolidation_audit_trail', ['event_type'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_consolidation_audit_type', table_name='consolidation_audit_trail')
    op.drop_index('idx_consolidation_audit_timestamp', table_name='consolidation_audit_trail')
    op.drop_index('idx_consolidation_audit_consolidation', table_name='consolidation_audit_trail')
    op.drop_index('idx_consolidated_date', table_name='consolidated_emissions')
    op.drop_index('idx_consolidated_status', table_name='consolidated_emissions')
    op.drop_index('idx_consolidated_company_year', table_name='consolidated_emissions')
    
    # Drop tables
    op.drop_table('consolidation_audit_trail')
    op.drop_table('consolidated_emissions')