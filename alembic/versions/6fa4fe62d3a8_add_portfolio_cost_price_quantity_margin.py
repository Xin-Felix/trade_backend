"""add portfolio cost price quantity margin

Revision ID: 6fa4fe62d3a8
Revises: b25892702575
Create Date: 2026-07-12 20:56:26.188674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fa4fe62d3a8'
down_revision: Union[str, None] = 'b25892702575'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'portfolio',
        sa.Column('cost_price', sa.Numeric(precision=12, scale=4), nullable=True, comment='成本价')
    )
    op.add_column(
        'portfolio',
        sa.Column('quantity', sa.Numeric(precision=15, scale=4), nullable=True, comment='持仓数量（股数）')
    )
    op.add_column(
        'portfolio',
        sa.Column('is_margin', sa.Boolean(), server_default=sa.text('false'), nullable=True, comment='是否融资持仓')
    )


def downgrade() -> None:
    op.drop_column('portfolio', 'is_margin')
    op.drop_column('portfolio', 'quantity')
    op.drop_column('portfolio', 'cost_price')
