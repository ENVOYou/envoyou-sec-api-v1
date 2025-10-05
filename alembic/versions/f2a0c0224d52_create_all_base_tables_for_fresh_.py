"""Create all base tables for fresh PostgreSQL database

Revision ID: f2a0c0224d52
Revises: 38e45b2a7341
Create Date: 2025-10-05 17:45:59.394511

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a0c0224d52'
down_revision = None  # This should be the first migration for PostgreSQL
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table (referenced by foreign keys)
    op.create_table('users',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    
    # Create companies table
    op.create_table('companies',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('ticker', sa.String(10), nullable=True),
        sa.Column('cik', sa.String(20), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('headquarters_country', sa.String(100), nullable=False, default='United States'),
        sa.Column('fiscal_year_end', sa.String(10), nullable=True),
        sa.Column('reporting_year', sa.Integer(), nullable=False),
        sa.Column('is_public_company', sa.Boolean(), nullable=False, default=True),
        sa.Column('market_cap_category', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_companies_name', 'companies', ['name'])
    op.create_index('ix_companies_ticker', 'companies', ['ticker'], unique=True)
    op.create_index('ix_companies_cik', 'companies', ['cik'], unique=True)
    op.create_index('ix_companies_reporting_year', 'companies', ['reporting_year'])
    
    # Create company_entities table
    op.create_table('company_entities',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('ownership_percentage', sa.Float(), nullable=False, default=100.0),
        sa.Column('consolidation_method', sa.String(50), nullable=False, default='full'),
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('state_province', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('primary_activity', sa.String(255), nullable=True),
        sa.Column('operational_control', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'])
    )
    op.create_index('ix_company_entities_company_id', 'company_entities', ['company_id'])
    
    # Create emissions_calculations table with all required fields
    op.create_table('emissions_calculations',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('calculation_name', sa.String(255), nullable=False),
        sa.Column('calculation_code', sa.String(100), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('scope', sa.String(20), nullable=False),
        sa.Column('method', sa.String(50), nullable=False),
        sa.Column('reporting_year', sa.Integer(), nullable=True),
        sa.Column('reporting_period_start', sa.Date(), nullable=True),
        sa.Column('reporting_period_end', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('calculated_by', sa.String(36), nullable=False),
        sa.Column('reviewed_by', sa.String(36), nullable=True),
        sa.Column('approved_by', sa.String(36), nullable=True),
        sa.Column('total_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_scope1_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_scope2_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_scope3_co2e', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_co2', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_ch4', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('total_n2o', sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column('input_data', sa.Text(), nullable=False),
        sa.Column('calculation_parameters', sa.Text(), nullable=True),
        sa.Column('emission_factors_used', sa.Text(), nullable=False),
        sa.Column('data_quality_score', sa.Float(), nullable=True),
        sa.Column('uncertainty_percentage', sa.Float(), nullable=True),
        sa.Column('calculation_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('calculation_duration_seconds', sa.Float(), nullable=True),
        sa.Column('validation_errors', sa.Text(), nullable=True),
        sa.Column('validation_warnings', sa.Text(), nullable=True),
        sa.Column('source_documents', sa.Text(), nullable=True),
        sa.Column('third_party_verification', sa.Boolean(), nullable=False, default=False),
        sa.Column('validation_status', sa.String(50), nullable=True),
        sa.Column('calculation_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.ForeignKeyConstraint(['entity_id'], ['company_entities.id'])
    )
    op.create_index('ix_emissions_calculations_calculation_code', 'emissions_calculations', ['calculation_code'], unique=True)
    op.create_index('ix_emissions_calculations_company_id', 'emissions_calculations', ['company_id'])
    op.create_index('ix_emissions_calculations_entity_id', 'emissions_calculations', ['entity_id'])
    op.create_index('ix_emissions_calculations_scope', 'emissions_calculations', ['scope'])
    op.create_index('ix_emissions_calculations_status', 'emissions_calculations', ['status'])
    op.create_index('ix_emissions_calculations_reporting_year', 'emissions_calculations', ['reporting_year'])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table('emissions_calculations')
    op.drop_table('company_entities')
    op.drop_table('companies')
    op.drop_table('users')