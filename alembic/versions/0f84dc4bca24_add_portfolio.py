"""add_portfolio

Revision ID: 0f84dc4bca24
Revises: 8f9c7e6d2a41
Create Date: 2026-07-12 12:57:24.657561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f84dc4bca24'
down_revision: Union[str, None] = '8f9c7e6d2a41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'portfolio',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False, comment='用户 public_id'),
        sa.Column('ts_code', sa.String(length=20), nullable=False, comment='Tushare 标准代码，如 000001.SZ'),
        sa.Column('code', sa.String(length=20), nullable=False, comment='原始股票代码，如 000001'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='股票名称'),
        sa.Column('note', sa.String(length=500), nullable=True, comment='持仓备注'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='标记时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.public_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'ts_code', name='uq_portfolio_user_code')
    )
    op.create_index(op.f('ix_portfolio_user_id'), 'portfolio', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_user_id'), table_name='portfolio')
    op.drop_table('portfolio')
