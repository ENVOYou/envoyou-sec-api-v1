"""Add is_active field to company_entities

Revision ID: 38e45b2a7341
Revises: 2e6ca0c284c6
Create Date: 2025-10-05 17:26:45.492723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '38e45b2a7341'
down_revision = '2e6ca0c284c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active field to company_entities
    op.add_column('company_entities', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
    
    # Update existing entities to be active
    op.execute("UPDATE company_entities SET is_active = 1 WHERE is_active IS NULL")


def downgrade() -> None:
    # Remove is_active field
    op.drop_column('company_entities', 'is_active')