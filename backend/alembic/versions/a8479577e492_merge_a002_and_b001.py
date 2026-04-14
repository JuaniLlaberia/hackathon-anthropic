"""merge_a002_and_b001

Revision ID: a8479577e492
Revises: a002add_ml_auth, c7cbf1a3b951
Create Date: 2026-04-14 18:20:11.915609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8479577e492'
down_revision: Union[str, None] = ('a002add_ml_auth', 'c7cbf1a3b951')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
