"""Add workflow tables

Revision ID: workflow_tables_001
Revises: 5e0f57431a95
Create Date: 2025-10-05 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'workflow_tables_001'
down_revision = '5e0f57431a95'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workflow_templates table
    op.create_table('workflow_templates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('workflow_type', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('steps_config', sa.Text(), nullable=False),  # JSON as TEXT for SQLite
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create workflows table
    op.create_table('workflows',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('template_id', sa.String(36), nullable=False),
        sa.Column('subject_type', sa.String(100), nullable=False),
        sa.Column('subject_id', sa.String(36), nullable=False),
        sa.Column('current_state', sa.String(50), nullable=False, default='draft'),
        sa.Column('current_step', sa.String(100), nullable=True),
        sa.Column('initiated_by', sa.String(36), nullable=False),
        sa.Column('initiated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('priority', sa.String(20), nullable=False, default='normal'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('workflow_metadata', sa.Text(), nullable=True),  # JSON as TEXT for SQLite
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.ForeignKeyConstraint(['template_id'], ['workflow_templates.id']),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subject_type', 'subject_id', name='uq_workflow_subject')
    )

    # Create approval_requests table
    op.create_table('approval_requests',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('sequence_order', sa.Integer(), nullable=False),
        sa.Column('assigned_to', sa.String(36), nullable=False),
        sa.Column('assigned_role', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('action_taken', sa.String(50), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('response_metadata', sa.Text(), nullable=True),  # JSON as TEXT for SQLite
        sa.Column('delegated_to', sa.String(36), nullable=True),
        sa.Column('delegation_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id']),
        sa.ForeignKeyConstraint(['delegated_to'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create workflow_history table
    op.create_table('workflow_history',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('from_state', sa.String(50), nullable=True),
        sa.Column('to_state', sa.String(50), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('actor_id', sa.String(36), nullable=False),
        sa.Column('actor_role', sa.String(50), nullable=False),
        sa.Column('change_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('change_metadata', sa.Text(), nullable=True),  # JSON as TEXT for SQLite
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create notification_queue table
    op.create_table('notification_queue',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('workflow_id', sa.String(36), nullable=False),
        sa.Column('recipient_id', sa.String(36), nullable=False),
        sa.Column('notification_type', sa.String(100), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivery_method', sa.String(50), nullable=False, default='email'),
        sa.Column('delivery_metadata', sa.Text(), nullable=True),  # JSON as TEXT for SQLite
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('notification_queue')
    op.drop_table('workflow_history')
    op.drop_table('approval_requests')
    op.drop_table('workflows')
    op.drop_table('workflow_templates')