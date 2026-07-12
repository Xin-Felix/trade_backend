"""Add company details to stock_basic

Revision ID: f973e8b1d2e1
Revises: 612d2e772bd1
Create Date: 2026-07-11 23:28:57.618095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f973e8b1d2e1'
down_revision: Union[str, None] = '612d2e772bd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stock_basic', sa.Column('province', sa.String(length=50), nullable=True, comment='所在省份'))
    op.add_column('stock_basic', sa.Column('city', sa.String(length=50), nullable=True, comment='所在城市'))
    op.add_column('stock_basic', sa.Column('introduction', sa.Text(), nullable=True, comment='公司介绍'))
    op.add_column('stock_basic', sa.Column('main_business', sa.Text(), nullable=True, comment='主要业务及产品'))
    op.add_column('stock_basic', sa.Column('website', sa.String(length=200), nullable=True, comment='公司主页'))
    op.add_column('stock_basic', sa.Column('chairman', sa.String(length=100), nullable=True, comment='法人代表/董事长'))
    op.add_column('stock_basic', sa.Column('reg_capital', sa.String(length=50), nullable=True, comment='注册资本'))
    op.add_column('stock_basic', sa.Column('setup_date', sa.Date(), nullable=True, comment='成立日期'))
    op.add_column('stock_basic', sa.Column('employees', sa.Integer(), nullable=True, comment='员工人数'))


def downgrade() -> None:
    op.drop_column('stock_basic', 'employees')
    op.drop_column('stock_basic', 'setup_date')
    op.drop_column('stock_basic', 'reg_capital')
    op.drop_column('stock_basic', 'chairman')
    op.drop_column('stock_basic', 'website')
    op.drop_column('stock_basic', 'main_business')
    op.drop_column('stock_basic', 'introduction')
    op.drop_column('stock_basic', 'city')
    op.drop_column('stock_basic', 'province')
