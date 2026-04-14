"""a_003_add_agent_session_data

Add data JSON column to agent_sessions for conversation history.

Revision ID: a003agent_data
Revises: a002add_ml_auth
Create Date: 2026-04-14 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a003agent_data'
down_revision: Union[str, None] = 'a002add_ml_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agent_sessions', sa.Column('data', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('agent_sessions', 'data')
