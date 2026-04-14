"""a_002_add_ml_auth_fields

Add MercadoLibre OAuth fields to users table and state column to onboarding_sessions.

Revision ID: a002add_ml_auth
Revises: 400b93115cfb
Create Date: 2026-04-14 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a002add_ml_auth'
down_revision: Union[str, None] = 'c7cbf1a3b951'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ML OAuth columns on users
    op.add_column('users', sa.Column('ml_user_id', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('ml_access_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('ml_refresh_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('ml_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('ml_connected', sa.Boolean(), server_default='false', nullable=True))

    # State column on onboarding_sessions
    op.add_column('onboarding_sessions', sa.Column('state', sa.String(length=30), server_default='welcome', nullable=True))


def downgrade() -> None:
    op.drop_column('onboarding_sessions', 'state')
    op.drop_column('users', 'ml_connected')
    op.drop_column('users', 'ml_token_expires_at')
    op.drop_column('users', 'ml_refresh_token')
    op.drop_column('users', 'ml_access_token')
    op.drop_column('users', 'ml_user_id')
