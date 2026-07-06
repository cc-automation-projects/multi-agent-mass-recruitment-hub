"""add model_weights table

Revision ID: 002
Revises: 001
Create Date: 2026-06-13 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'model_weights',
        sa.Column('id', sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column('model_name', sa.String(64), nullable=False),
        sa.Column('weights', JSONB(), nullable=False),
        sa.Column('created_by', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        "INSERT INTO model_weights (model_name, weights) VALUES "
        "('propensity_dialer', '{\"experience\": 0.3, \"education\": 0.2, \"region\": 0.1, \"skill_match\": 0.4}')"
    )


def downgrade() -> None:
    op.drop_table('model_weights')
