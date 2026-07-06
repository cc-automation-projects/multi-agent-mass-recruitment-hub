"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-13 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблица candidates
    op.create_table(
        'candidates',
        sa.Column('id', sa.String(64), primary_key=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=False, index=True),
        sa.Column('consent_152fz', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('consent_biometry', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resume_text', sa.Text(), nullable=True),
        sa.Column('screening_status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Таблица call_logs
    op.create_table(
        'call_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('candidate_id', sa.String(64), nullable=False, index=True),
        sa.Column('call_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(32), nullable=False),  # answered, no_answer, failed
        sa.Column('recording_url', sa.String(512), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
    )

    # Таблица interview_results
    op.create_table(
        'interview_results',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('candidate_id', sa.String(64), nullable=False, index=True),
        sa.Column('overall_score', sa.Numeric(3, 2), nullable=False),
        sa.Column('motivation_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('communication_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('consistency_score', sa.Numeric(3, 2), nullable=True),
        sa.Column('prosody', JSONB(), nullable=True),
        sa.Column('recommendation', sa.String(32), nullable=True),
        sa.Column('interview_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
    )

    # Таблица audit_logs (структурированные логи для 152-ФЗ)
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('candidate_id', sa.String(64), nullable=False, index=True),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('decision', sa.String(32), nullable=True),
        sa.Column('user_id', sa.String(64), nullable=True),
        sa.Column('session_id', sa.String(64), nullable=True),
        sa.Column('metadata', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),  # soft delete
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_audit_logs_candidate_action', 'audit_logs', ['candidate_id', 'action'])

    # Таблица fairness_reports
    op.create_table(
        'fairness_reports',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('report_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('demographic_parity', sa.Numeric(5, 4), nullable=True),
        sa.Column('disparate_impact', sa.Numeric(5, 4), nullable=True),
        sa.Column('false_rejection_rate', sa.Numeric(5, 4), nullable=True),
        sa.Column('rejection_rates', JSONB(), nullable=True),
        sa.Column('requires_review', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('idx_fairness_reports_date', 'fairness_reports', ['report_date'])


def downgrade() -> None:
    op.drop_table('fairness_reports')
    op.drop_table('audit_logs')
    op.drop_table('interview_results')
    op.drop_table('call_logs')
    op.drop_table('candidates')
