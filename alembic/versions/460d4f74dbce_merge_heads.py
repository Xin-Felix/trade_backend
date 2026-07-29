"""merge_heads

Revision ID: 460d4f74dbce
Revises: 0b9b8270972e, b2c3d4e5f6a7
Create Date: 2026-07-14 20:47:20.837886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '460d4f74dbce'
down_revision: Union[str, None] = ('0b9b8270972e', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
