"""add users table

Revision ID: 003
Revises: 002
Create Date: 2026-06-13 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False, unique=True),
        sa.Column('email', sa.String(128), nullable=False, unique=True),
        sa.Column('hashed_password', sa.String(256), nullable=False),
        sa.Column('role', sa.String(32), nullable=False, server_default='hr'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = pwd_context.hash("admin")
    op.execute(
        f"INSERT INTO users (id, username, email, hashed_password, role) VALUES "
        f"('admin', 'admin', 'admin@massrecruithub.ru', '{hashed}', 'admin')"
    )


def downgrade() -> None:
    op.drop_table('users')
