"""add index_global table

Revision ID: a1b2c3d4e5f6
Revises: 82c6daf1bd1d
Create Date: 2026-07-13 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '82c6daf1bd1d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'index_global',
        sa.Column('ts_code', sa.String(20), nullable=False, comment='指数代码，如 DJI/SPX/HSI'),
        sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
        sa.Column('open', sa.Numeric(20, 4), nullable=True, comment='开盘价'),
        sa.Column('close', sa.Numeric(20, 4), nullable=True, comment='收盘价'),
        sa.Column('high', sa.Numeric(20, 4), nullable=True, comment='最高价'),
        sa.Column('low', sa.Numeric(20, 4), nullable=True, comment='最低价'),
        sa.Column('pre_close', sa.Numeric(20, 4), nullable=True, comment='昨收价'),
        sa.Column('change', sa.Numeric(20, 4), nullable=True, comment='涨跌额'),
        sa.Column('pct_chg', sa.Numeric(20, 4), nullable=True, comment='涨跌幅(%)'),
        sa.Column('swing', sa.Numeric(20, 4), nullable=True, comment='振幅(%)'),
        sa.Column('vol', sa.Numeric(20, 4), nullable=True, comment='成交量'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('ts_code', 'trade_date'),
        sa.UniqueConstraint('ts_code', 'trade_date', name='uix_index_global'),
    )


def downgrade() -> None:
    op.drop_table('index_global')
