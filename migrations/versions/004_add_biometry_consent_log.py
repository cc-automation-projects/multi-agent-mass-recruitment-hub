"""add biometry_consent_log table

Revision ID: 004
Revises: 003
Create Date: 2026-06-13 21:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'biometry_consent_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('candidate_id', sa.String(64), nullable=False, index=True),
        sa.Column('consent_given', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('audio_hash', sa.String(64), nullable=False, comment='SHA256 of audio fragment with consent'),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_biometry_consent_candidate', 'biometry_consent_log', ['candidate_id'])


def downgrade() -> None:
    op.drop_table('biometry_consent_log')
