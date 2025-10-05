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
    # This migration is now redundant since base migration includes all fields
    # Just update existing records if any
    
    # Update existing records to have calculation_date = created_at and reporting_year = 2024
    op.execute("UPDATE emissions_calculations SET calculation_date = created_at WHERE calculation_date IS NULL")
    op.execute("UPDATE emissions_calculations SET reporting_year = 2024 WHERE reporting_year IS NULL")
    
    # Update existing entities to be active (PostgreSQL compatible)
    op.execute("UPDATE company_entities SET is_active = TRUE WHERE is_active IS NULL")


def downgrade() -> None:
    # No fields to remove since they're part of base migration
    pass