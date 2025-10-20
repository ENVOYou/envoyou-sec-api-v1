"""Add email verification fields to existing users table

Revision ID: a8a47ea9362b
Revises: 00cba2a7ee84
Create Date: 2025-10-20 23:20:06.852128

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8a47ea9362b"
down_revision: Union[str, None] = "00cba2a7ee84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email verification fields to existing users table
    op.add_column(
        "users",
        sa.Column("email_verification_token", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verification_token_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "email_verified", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # Remove email verification fields from users table
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email_verification_token_expires")
    op.drop_column("users", "email_verification_token")
    # ### end Alembic commands ###
    op.create_table(
        "audit_anomalies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("anomaly_id", sa.String(length=255), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("anomaly_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("affected_entries", sa.JSON(), nullable=True),
        sa.Column("risk_assessment", sa.Text(), nullable=True),
        sa.Column("recommended_actions", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(length=255), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_anomaly_status_detected",
        "audit_anomalies",
        ["status", "detected_at"],
        unique=False,
    )
    op.create_index(
        "idx_anomaly_type_severity",
        "audit_anomalies",
        ["anomaly_type", "severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_anomalies_anomaly_id"),
        "audit_anomalies",
        ["anomaly_id"],
        unique=True,
    )
    op.create_table(
        "audit_configuration",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("config_key", sa.String(length=255), nullable=False),
        sa.Column("config_value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_configuration_config_key"),
        "audit_configuration",
        ["config_key"],
        unique=True,
    )
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_audit_entity", "audit_entries", ["entity_type", "entity_id"], unique=False
    )
    op.create_index("idx_audit_session", "audit_entries", ["session_id"], unique=False)
    op.create_index(
        "idx_audit_timestamp_action",
        "audit_entries",
        ["timestamp", "action"],
        unique=False,
    )
    op.create_index(
        "idx_audit_user_timestamp",
        "audit_entries",
        ["user_id", "timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_entries_action"), "audit_entries", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_audit_entries_entity_id"), "audit_entries", ["entity_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_entries_entity_type"),
        "audit_entries",
        ["entity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_entries_session_id"),
        "audit_entries",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_entries_timestamp"), "audit_entries", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_audit_entries_user_id"), "audit_entries", ["user_id"], unique=False
    )
    op.create_table(
        "audit_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.String(length=255), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("date_range_start", sa.DateTime(), nullable=True),
        sa.Column("date_range_end", sa.DateTime(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("summary_stats", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=True),
        sa.Column("last_downloaded_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_report_generated_by",
        "audit_reports",
        ["generated_by", "generated_at"],
        unique=False,
    )
    op.create_index(
        "idx_report_type_generated",
        "audit_reports",
        ["report_type", "generated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_audit_reports_report_id"), "audit_reports", ["report_id"], unique=True
    )
    op.create_table(
        "audit_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("session_purpose", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_audit_session_expires", "audit_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        "idx_audit_session_user", "audit_sessions", ["user_id", "status"], unique=False
    )
    op.create_index(
        op.f("ix_audit_sessions_user_id"), "audit_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=True),
        sa.Column("cik", sa.String(length=20), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("sector", sa.String(length=100), nullable=True),
        sa.Column("headquarters_country", sa.String(length=100), nullable=False),
        sa.Column("fiscal_year_end", sa.String(length=10), nullable=True),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("is_public_company", sa.Boolean(), nullable=False),
        sa.Column("market_cap_category", sa.String(length=50), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_cik"), "companies", ["cik"], unique=True)
    op.create_index(op.f("ix_companies_name"), "companies", ["name"], unique=False)
    op.create_index(
        op.f("ix_companies_reporting_year"),
        "companies",
        ["reporting_year"],
        unique=False,
    )
    op.create_index(op.f("ix_companies_ticker"), "companies", ["ticker"], unique=True)
    op.create_table(
        "data_lineage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("parent_entity_type", sa.String(length=100), nullable=True),
        sa.Column("parent_entity_id", sa.String(length=255), nullable=True),
        sa.Column("transformation_type", sa.String(length=100), nullable=True),
        sa.Column("transformation_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("audit_metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lineage_created", "data_lineage", ["created_at"], unique=False)
    op.create_index(
        "idx_lineage_entity", "data_lineage", ["entity_type", "entity_id"], unique=False
    )
    op.create_index(
        "idx_lineage_parent",
        "data_lineage",
        ["parent_entity_type", "parent_entity_id"],
        unique=False,
    )
    op.create_table(
        "emission_factors",
        sa.Column("factor_name", sa.String(length=255), nullable=False),
        sa.Column("factor_code", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("fuel_type", sa.String(length=50), nullable=True),
        sa.Column("electricity_region", sa.String(length=10), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("co2_factor", sa.Float(), nullable=False),
        sa.Column("ch4_factor", sa.Float(), nullable=True),
        sa.Column("n2o_factor", sa.Float(), nullable=True),
        sa.Column("co2e_factor", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_document", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("uncertainty", sa.Float(), nullable=True),
        sa.Column("additional_data", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_emission_factors_current",
        "emission_factors",
        ["category", "is_current"],
        unique=False,
    )
    op.create_index(
        "idx_emission_factors_fuel",
        "emission_factors",
        ["fuel_type", "is_current"],
        unique=False,
    )
    op.create_index(
        "idx_emission_factors_region",
        "emission_factors",
        ["electricity_region", "is_current"],
        unique=False,
    )
    op.create_index(
        "idx_emission_factors_version",
        "emission_factors",
        ["factor_code", "version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_category"),
        "emission_factors",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_factor_code"),
        "emission_factors",
        ["factor_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_factor_name"),
        "emission_factors",
        ["factor_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_is_current"),
        "emission_factors",
        ["is_current"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_publication_year"),
        "emission_factors",
        ["publication_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_source"), "emission_factors", ["source"], unique=False
    )
    op.create_index(
        op.f("ix_emission_factors_valid_from"),
        "emission_factors",
        ["valid_from"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_valid_to"),
        "emission_factors",
        ["valid_to"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emission_factors_version"),
        "emission_factors",
        ["version"],
        unique=False,
    )
    op.create_table(
        "epa_data_updates",
        sa.Column("update_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column(
            "update_date",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("records_added", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_deprecated", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("source_file", sa.String(length=500), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("validation_passed", sa.Boolean(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_epa_data_updates_update_type"),
        "epa_data_updates",
        ["update_type"],
        unique=False,
    )
    op.create_table(
        "epa_data_validations",
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_description", sa.Text(), nullable=False),
        sa.Column("rule_type", sa.String(length=50), nullable=False),
        sa.Column("rule_parameters", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_checked", sa.Integer(), nullable=False),
        sa.Column("records_passed", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_epa_data_validations_rule_name"),
        "epa_data_validations",
        ["rule_name"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "INACTIVE",
                "SUSPENDED",
                "PENDING_ACTIVATION",
                name="userstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.Enum(
                "CFO",
                "GENERAL_COUNSEL",
                "FINANCE_TEAM",
                "AUDITOR",
                "ADMIN",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.String(length=10), nullable=False),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("email_verification_token", sa.String(length=255), nullable=True),
        sa.Column(
            "email_verification_token_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_company_id"), "users", ["company_id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_is_deleted"), "users", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_table(
        "workflow_templates",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("steps_config", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "company_entities",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("ownership_percentage", sa.Float(), nullable=False),
        sa.Column("consolidation_method", sa.String(length=50), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("state_province", sa.String(length=100), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("primary_activity", sa.String(length=255), nullable=True),
        sa.Column("operational_control", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_company_entity_company_active",
        "company_entities",
        ["company_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_company_entity_ownership",
        "company_entities",
        ["ownership_percentage"],
        unique=False,
    )
    op.create_index(
        "idx_company_entity_type", "company_entities", ["entity_type"], unique=False
    )
    op.create_index(
        op.f("ix_company_entities_company_id"),
        "company_entities",
        ["company_id"],
        unique=False,
    )
    op.create_table(
        "consolidated_emissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("reporting_period_start", sa.Date(), nullable=False),
        sa.Column("reporting_period_end", sa.Date(), nullable=False),
        sa.Column("consolidation_method", sa.String(length=50), nullable=False),
        sa.Column("consolidation_date", sa.DateTime(), nullable=False),
        sa.Column("consolidation_version", sa.Integer(), nullable=False),
        sa.Column(
            "total_scope1_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column(
            "total_scope2_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column(
            "total_scope3_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column("total_co2e", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("total_co2", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("total_ch4_co2e", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("total_n2o_co2e", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column(
            "total_other_ghg_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column("total_entities_included", sa.Integer(), nullable=False),
        sa.Column("entities_with_scope1", sa.Integer(), nullable=False),
        sa.Column("entities_with_scope2", sa.Integer(), nullable=False),
        sa.Column("entities_with_scope3", sa.Integer(), nullable=False),
        sa.Column(
            "data_completeness_score", sa.Numeric(precision=5, scale=2), nullable=True
        ),
        sa.Column(
            "consolidation_confidence_score",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
        sa.Column("entity_contributions", sa.JSON(), nullable=True),
        sa.Column("consolidation_adjustments", sa.JSON(), nullable=True),
        sa.Column("exclusions", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=True),
        sa.Column("validation_notes", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "reporting_year",
            "consolidation_version",
            name="uq_consolidated_company_year_version",
        ),
    )
    op.create_index(
        "idx_consolidated_company_year",
        "consolidated_emissions",
        ["company_id", "reporting_year"],
        unique=False,
    )
    op.create_index(
        "idx_consolidated_date",
        "consolidated_emissions",
        ["consolidation_date"],
        unique=False,
    )
    op.create_index(
        "idx_consolidated_status", "consolidated_emissions", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_consolidated_emissions_company_id"),
        "consolidated_emissions",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_consolidated_emissions_reporting_year"),
        "consolidated_emissions",
        ["reporting_year"],
        unique=False,
    )
    op.create_table(
        "workflows",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=100), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column(
            "current_state",
            sa.Enum(
                "DRAFT",
                "PENDING_FINANCE_APPROVAL",
                "PENDING_LEGAL_APPROVAL",
                "PENDING_CFO_APPROVAL",
                "APPROVED",
                "REJECTED",
                "UNDER_AUDIT",
                "SUBMITTED_TO_SEC",
                name="workflowstate",
            ),
            nullable=False,
        ),
        sa.Column("current_step", sa.String(length=100), nullable=True),
        sa.Column("initiated_by", sa.UUID(), nullable=False),
        sa.Column(
            "initiated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["initiated_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["workflow_templates.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_type", "subject_id", name="uq_workflow_subject"),
    )
    op.create_table(
        "approval_requests",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=False),
        sa.Column(
            "assigned_role",
            sa.Enum(
                "CFO",
                "GENERAL_COUNSEL",
                "FINANCE_TEAM",
                "AUDITOR",
                "ADMIN",
                "SUBMITTER",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column(
            "action_taken",
            sa.Enum(
                "APPROVE",
                "REJECT",
                "REQUEST_CHANGES",
                "DELEGATE",
                name="approvalaction",
            ),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("response_metadata", sa.JSON(), nullable=True),
        sa.Column("delegated_to", sa.UUID(), nullable=True),
        sa.Column("delegation_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["delegated_to"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "consolidation_audit_trail",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("consolidation_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("event_description", sa.Text(), nullable=True),
        sa.Column("before_values", sa.JSON(), nullable=True),
        sa.Column("after_values", sa.JSON(), nullable=True),
        sa.Column("affected_entities", sa.JSON(), nullable=True),
        sa.Column("system_info", sa.JSON(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["consolidation_id"],
            ["consolidated_emissions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_consolidation_audit_consolidation",
        "consolidation_audit_trail",
        ["consolidation_id"],
        unique=False,
    )
    op.create_index(
        "idx_consolidation_audit_timestamp",
        "consolidation_audit_trail",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_consolidation_audit_type",
        "consolidation_audit_trail",
        ["event_type"],
        unique=False,
    )
    op.create_table(
        "emissions_calculations",
        sa.Column("calculation_name", sa.String(length=255), nullable=False),
        sa.Column("calculation_code", sa.String(length=100), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=True),
        sa.Column("reporting_period_start", sa.Date(), nullable=True),
        sa.Column("reporting_period_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("calculated_by", sa.UUID(), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("total_co2e", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column(
            "total_scope1_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column(
            "total_scope2_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column(
            "total_scope3_co2e", sa.Numeric(precision=15, scale=3), nullable=True
        ),
        sa.Column("total_co2", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("total_ch4", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("total_n2o", sa.Numeric(precision=15, scale=3), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("calculation_parameters", sa.JSON(), nullable=True),
        sa.Column("emission_factors_used", sa.JSON(), nullable=False),
        sa.Column("data_quality_score", sa.Float(), nullable=True),
        sa.Column("uncertainty_percentage", sa.Float(), nullable=True),
        sa.Column(
            "calculation_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("calculation_duration_seconds", sa.Float(), nullable=True),
        sa.Column("validation_errors", sa.JSON(), nullable=True),
        sa.Column("validation_warnings", sa.JSON(), nullable=True),
        sa.Column("encrypted_input_data", sa.Text(), nullable=True),
        sa.Column("encrypted_emission_factors", sa.Text(), nullable=True),
        sa.Column("data_integrity_hash", sa.String(length=64), nullable=True),
        sa.Column("source_documents", sa.JSON(), nullable=True),
        sa.Column("third_party_verification", sa.Boolean(), nullable=False),
        sa.Column("validation_status", sa.String(length=50), nullable=True),
        sa.Column("calculation_date", sa.DateTime(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["company_entities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_emissions_calc_approved",
        "emissions_calculations",
        ["approved_by", "status"],
        unique=False,
    )
    op.create_index(
        "idx_emissions_calc_company_scope",
        "emissions_calculations",
        ["company_id", "scope"],
        unique=False,
    )
    op.create_index(
        "idx_emissions_calc_status_date",
        "emissions_calculations",
        ["status", "calculation_timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_emissions_calc_year_scope",
        "emissions_calculations",
        ["reporting_year", "scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emissions_calculations_calculation_code"),
        "emissions_calculations",
        ["calculation_code"],
        unique=True,
    )
    op.create_index(
        op.f("ix_emissions_calculations_company_id"),
        "emissions_calculations",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emissions_calculations_entity_id"),
        "emissions_calculations",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emissions_calculations_reporting_year"),
        "emissions_calculations",
        ["reporting_year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emissions_calculations_scope"),
        "emissions_calculations",
        ["scope"],
        unique=False,
    )
    op.create_index(
        op.f("ix_emissions_calculations_status"),
        "emissions_calculations",
        ["status"],
        unique=False,
    )
    op.create_table(
        "notification_queue",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("notification_type", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_method", sa.String(length=50), nullable=False),
        sa.Column("delivery_metadata", sa.JSON(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("report_metadata", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("excel_path", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "workflow_history",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column(
            "from_state",
            sa.Enum(
                "DRAFT",
                "PENDING_FINANCE_APPROVAL",
                "PENDING_LEGAL_APPROVAL",
                "PENDING_CFO_APPROVAL",
                "APPROVED",
                "REJECTED",
                "UNDER_AUDIT",
                "SUBMITTED_TO_SEC",
                name="workflowstate",
            ),
            nullable=True,
        ),
        sa.Column(
            "to_state",
            sa.Enum(
                "DRAFT",
                "PENDING_FINANCE_APPROVAL",
                "PENDING_LEGAL_APPROVAL",
                "PENDING_CFO_APPROVAL",
                "APPROVED",
                "REJECTED",
                "UNDER_AUDIT",
                "SUBMITTED_TO_SEC",
                name="workflowstate",
            ),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column(
            "actor_role",
            sa.Enum(
                "CFO",
                "GENERAL_COUNSEL",
                "FINANCE_TEAM",
                "AUDITOR",
                "ADMIN",
                "SUBMITTER",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column(
            "change_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("change_metadata", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "activity_data",
        sa.Column("calculation_id", sa.UUID(), nullable=False),
        sa.Column("activity_type", sa.String(length=100), nullable=False),
        sa.Column("fuel_type", sa.String(length=50), nullable=True),
        sa.Column("activity_description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("activity_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activity_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_source", sa.String(length=255), nullable=True),
        sa.Column("data_quality", sa.String(length=50), nullable=True),
        sa.Column("measurement_method", sa.String(length=255), nullable=True),
        sa.Column("emission_factor_id", sa.UUID(), nullable=True),
        sa.Column("emission_factor_value", sa.Float(), nullable=False),
        sa.Column("emission_factor_unit", sa.String(length=100), nullable=False),
        sa.Column("emission_factor_source", sa.String(length=100), nullable=False),
        sa.Column("co2_emissions", sa.Float(), nullable=True),
        sa.Column("ch4_emissions", sa.Float(), nullable=True),
        sa.Column("n2o_emissions", sa.Float(), nullable=True),
        sa.Column("co2e_emissions", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("additional_data", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["calculation_id"],
            ["emissions_calculations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_activity_calculation_type",
        "activity_data",
        ["calculation_id", "activity_type"],
        unique=False,
    )
    op.create_index(
        "idx_activity_fuel_type", "activity_data", ["fuel_type"], unique=False
    )
    op.create_index(
        "idx_activity_location", "activity_data", ["location"], unique=False
    )
    op.create_index(
        op.f("ix_activity_data_activity_type"),
        "activity_data",
        ["activity_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_activity_data_calculation_id"),
        "activity_data",
        ["calculation_id"],
        unique=False,
    )
    op.create_table(
        "calculation_audit_trails",
        sa.Column("calculation_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_description", sa.Text(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("user_role", sa.String(length=50), nullable=False),
        sa.Column(
            "event_timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("field_changed", sa.String(length=100), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("additional_metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["calculation_id"],
            ["emissions_calculations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_calculation_audit_trails_calculation_id"),
        "calculation_audit_trails",
        ["calculation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_audit_trails_event_timestamp"),
        "calculation_audit_trails",
        ["event_timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_calculation_audit_trails_event_type"),
        "calculation_audit_trails",
        ["event_type"],
        unique=False,
    )
    op.create_table(
        "comments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("comment_type", sa.String(length=50), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=True),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["comments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_comments_report_id"), "comments", ["report_id"], unique=False
    )
    op.create_index(op.f("ix_comments_user_id"), "comments", ["user_id"], unique=False)
    op.create_table(
        "report_locks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("locked_by", sa.String(length=36), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("lock_reason", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("unlocked_at", sa.DateTime(), nullable=True),
        sa.Column("unlocked_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["locked_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
        ),
        sa.ForeignKeyConstraint(
            ["unlocked_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_report_locks_report_id"), "report_locks", ["report_id"], unique=False
    )
    op.create_table(
        "revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("changed_by", sa.String(length=36), nullable=False),
        sa.Column("change_type", sa.String(length=50), nullable=False),
        sa.Column("changes_summary", sa.Text(), nullable=True),
        sa.Column("previous_version", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["changed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_revisions_report_id"), "revisions", ["report_id"], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_revisions_report_id"), table_name="revisions")
    op.drop_table("revisions")
    op.drop_index(op.f("ix_report_locks_report_id"), table_name="report_locks")
    op.drop_table("report_locks")
    op.drop_index(op.f("ix_comments_user_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_report_id"), table_name="comments")
    op.drop_table("comments")
    op.drop_index(
        op.f("ix_calculation_audit_trails_event_type"),
        table_name="calculation_audit_trails",
    )
    op.drop_index(
        op.f("ix_calculation_audit_trails_event_timestamp"),
        table_name="calculation_audit_trails",
    )
    op.drop_index(
        op.f("ix_calculation_audit_trails_calculation_id"),
        table_name="calculation_audit_trails",
    )
    op.drop_table("calculation_audit_trails")
    op.drop_index(op.f("ix_activity_data_calculation_id"), table_name="activity_data")
    op.drop_index(op.f("ix_activity_data_activity_type"), table_name="activity_data")
    op.drop_index("idx_activity_location", table_name="activity_data")
    op.drop_index("idx_activity_fuel_type", table_name="activity_data")
    op.drop_index("idx_activity_calculation_type", table_name="activity_data")
    op.drop_table("activity_data")
    op.drop_table("workflow_history")
    op.drop_table("reports")
    op.drop_table("notification_queue")
    op.drop_index(
        op.f("ix_emissions_calculations_status"), table_name="emissions_calculations"
    )
    op.drop_index(
        op.f("ix_emissions_calculations_scope"), table_name="emissions_calculations"
    )
    op.drop_index(
        op.f("ix_emissions_calculations_reporting_year"),
        table_name="emissions_calculations",
    )
    op.drop_index(
        op.f("ix_emissions_calculations_entity_id"), table_name="emissions_calculations"
    )
    op.drop_index(
        op.f("ix_emissions_calculations_company_id"),
        table_name="emissions_calculations",
    )
    op.drop_index(
        op.f("ix_emissions_calculations_calculation_code"),
        table_name="emissions_calculations",
    )
    op.drop_index("idx_emissions_calc_year_scope", table_name="emissions_calculations")
    op.drop_index("idx_emissions_calc_status_date", table_name="emissions_calculations")
    op.drop_index(
        "idx_emissions_calc_company_scope", table_name="emissions_calculations"
    )
    op.drop_index("idx_emissions_calc_approved", table_name="emissions_calculations")
    op.drop_table("emissions_calculations")
    op.drop_index(
        "idx_consolidation_audit_type", table_name="consolidation_audit_trail"
    )
    op.drop_index(
        "idx_consolidation_audit_timestamp", table_name="consolidation_audit_trail"
    )
    op.drop_index(
        "idx_consolidation_audit_consolidation", table_name="consolidation_audit_trail"
    )
    op.drop_table("consolidation_audit_trail")
    op.drop_table("approval_requests")
    op.drop_table("workflows")
    op.drop_index(
        op.f("ix_consolidated_emissions_reporting_year"),
        table_name="consolidated_emissions",
    )
    op.drop_index(
        op.f("ix_consolidated_emissions_company_id"),
        table_name="consolidated_emissions",
    )
    op.drop_index("idx_consolidated_status", table_name="consolidated_emissions")
    op.drop_index("idx_consolidated_date", table_name="consolidated_emissions")
    op.drop_index("idx_consolidated_company_year", table_name="consolidated_emissions")
    op.drop_table("consolidated_emissions")
    op.drop_index(op.f("ix_company_entities_company_id"), table_name="company_entities")
    op.drop_index("idx_company_entity_type", table_name="company_entities")
    op.drop_index("idx_company_entity_ownership", table_name="company_entities")
    op.drop_index("idx_company_entity_company_active", table_name="company_entities")
    op.drop_table("company_entities")
    op.drop_table("workflow_templates")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_is_deleted"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_company_id"), table_name="users")
    op.drop_table("users")
    op.drop_index(
        op.f("ix_epa_data_validations_rule_name"), table_name="epa_data_validations"
    )
    op.drop_table("epa_data_validations")
    op.drop_index(
        op.f("ix_epa_data_updates_update_type"), table_name="epa_data_updates"
    )
    op.drop_table("epa_data_updates")
    op.drop_index(op.f("ix_emission_factors_version"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_valid_to"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_valid_from"), table_name="emission_factors")
    op.drop_index(op.f("ix_emission_factors_source"), table_name="emission_factors")
    op.drop_index(
        op.f("ix_emission_factors_publication_year"), table_name="emission_factors"
    )
    op.drop_index(op.f("ix_emission_factors_is_current"), table_name="emission_factors")
    op.drop_index(
        op.f("ix_emission_factors_factor_name"), table_name="emission_factors"
    )
    op.drop_index(
        op.f("ix_emission_factors_factor_code"), table_name="emission_factors"
    )
    op.drop_index(op.f("ix_emission_factors_category"), table_name="emission_factors")
    op.drop_index("idx_emission_factors_version", table_name="emission_factors")
    op.drop_index("idx_emission_factors_region", table_name="emission_factors")
    op.drop_index("idx_emission_factors_fuel", table_name="emission_factors")
    op.drop_index("idx_emission_factors_current", table_name="emission_factors")
    op.drop_table("emission_factors")
    op.drop_index("idx_lineage_parent", table_name="data_lineage")
    op.drop_index("idx_lineage_entity", table_name="data_lineage")
    op.drop_index("idx_lineage_created", table_name="data_lineage")
    op.drop_table("data_lineage")
    op.drop_index(op.f("ix_companies_ticker"), table_name="companies")
    op.drop_index(op.f("ix_companies_reporting_year"), table_name="companies")
    op.drop_index(op.f("ix_companies_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_cik"), table_name="companies")
    op.drop_table("companies")
    op.drop_index(op.f("ix_audit_sessions_user_id"), table_name="audit_sessions")
    op.drop_index("idx_audit_session_user", table_name="audit_sessions")
    op.drop_index("idx_audit_session_expires", table_name="audit_sessions")
    op.drop_table("audit_sessions")
    op.drop_index(op.f("ix_audit_reports_report_id"), table_name="audit_reports")
    op.drop_index("idx_report_type_generated", table_name="audit_reports")
    op.drop_index("idx_report_generated_by", table_name="audit_reports")
    op.drop_table("audit_reports")
    op.drop_index(op.f("ix_audit_entries_user_id"), table_name="audit_entries")
    op.drop_index(op.f("ix_audit_entries_timestamp"), table_name="audit_entries")
    op.drop_index(op.f("ix_audit_entries_session_id"), table_name="audit_entries")
    op.drop_index(op.f("ix_audit_entries_entity_type"), table_name="audit_entries")
    op.drop_index(op.f("ix_audit_entries_entity_id"), table_name="audit_entries")
    op.drop_index(op.f("ix_audit_entries_action"), table_name="audit_entries")
    op.drop_index("idx_audit_user_timestamp", table_name="audit_entries")
    op.drop_index("idx_audit_timestamp_action", table_name="audit_entries")
    op.drop_index("idx_audit_session", table_name="audit_entries")
    op.drop_index("idx_audit_entity", table_name="audit_entries")
    op.drop_table("audit_entries")
    op.drop_index(
        op.f("ix_audit_configuration_config_key"), table_name="audit_configuration"
    )
    op.drop_table("audit_configuration")
    op.drop_index(op.f("ix_audit_anomalies_anomaly_id"), table_name="audit_anomalies")
    op.drop_index("idx_anomaly_type_severity", table_name="audit_anomalies")
    op.drop_index("idx_anomaly_status_detected", table_name="audit_anomalies")
    op.drop_table("audit_anomalies")
    # ### end Alembic commands ###
