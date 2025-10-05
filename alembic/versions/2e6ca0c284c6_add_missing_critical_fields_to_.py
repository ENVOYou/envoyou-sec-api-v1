"""Add missing critical fields to emissions and entity tables

Revision ID: 2e6ca0c284c6
Revises: eda2517fe2c2
Create Date: 2025-10-05 17:23:32.700469

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2e6ca0c284c6'
down_revision = 'eda2517fe2c2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing critical fields for SEC compliance
    
    # Add scope-specific emissions fields (CRITICAL for SEC reporting)
    op.add_column('emissions_calculations', sa.Column('total_scope1_co2e', sa.Numeric(precision=15, scale=3), nullable=True))
    op.add_column('emissions_calculations', sa.Column('total_scope2_co2e', sa.Numeric(precision=15, scale=3), nullable=True))
    op.add_column('emissions_calculations', sa.Column('total_scope3_co2e', sa.Numeric(precision=15, scale=3), nullable=True))
    
    # Add validation status for audit compliance
    op.add_column('emissions_calculations', sa.Column('validation_status', sa.String(length=50), nullable=True))
    
    # Add calculation date - SQLite doesn't support NOT NULL with default, so we'll keep it nullable
    op.add_column('emissions_calculations', sa.Column('calculation_date', sa.DateTime(), nullable=True))
    
    # Add reporting year (CRITICAL for SEC compliance)
    op.add_column('emissions_calculations', sa.Column('reporting_year', sa.Integer(), nullable=True))
    
    # Update existing records to have calculation_date = created_at and reporting_year = 2024
    op.execute("UPDATE emissions_calculations SET calculation_date = created_at WHERE calculation_date IS NULL")
    op.execute("UPDATE emissions_calculations SET reporting_year = 2024 WHERE reporting_year IS NULL")
    
    # Add missing fields to company_entities for hierarchical structure
    op.add_column('company_entities', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
    
    # Update existing entities to be active
    op.execute("UPDATE company_entities SET is_active = 1 WHERE is_active IS NULL")


def downgrade() -> None:
    # Remove added fields
    op.drop_column('company_entities', 'is_active')
    op.drop_column('emissions_calculations', 'reporting_year')
    op.drop_column('emissions_calculations', 'calculation_date')
    op.drop_column('emissions_calculations', 'validation_status')
    op.drop_column('emissions_calculations', 'total_scope3_co2e')
    op.drop_column('emissions_calculations', 'total_scope2_co2e')
    op.drop_column('emissions_calculations', 'total_scope1_co2e')