"""add market_pulse table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'market_pulse',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False, comment='交易日期'),
        sa.Column('score', sa.Integer(), nullable=False, comment='市场温度 0~100'),
        sa.Column('level', sa.String(10), nullable=False, comment='等级'),
        sa.Column('summary', sa.Text(), nullable=True, comment='AI 一句话总结'),
        sa.Column('keywords', sa.String(500), nullable=True, comment='今日热点关键词，逗号分隔'),
        sa.Column('up_count', sa.Integer(), nullable=True, comment='上涨家数'),
        sa.Column('down_count', sa.Integer(), nullable=True, comment='下跌家数'),
        sa.Column('amount', sa.Numeric(20, 4), nullable=True, comment='成交额（亿元）'),
        sa.Column('amount_change_pct', sa.Numeric(10, 4), nullable=True, comment='成交额较昨日变化%'),
        sa.Column('north_money', sa.Numeric(20, 4), nullable=True, comment='北向资金净流入（亿元）'),
        sa.Column('limit_up_count', sa.Integer(), nullable=True, comment='涨停家数'),
        sa.Column('limit_down_count', sa.Integer(), nullable=True, comment='跌停家数'),
        sa.Column('open_limit_count', sa.Integer(), nullable=True, comment='炸板家数'),
        sa.Column('max_continuous_board', sa.Integer(), nullable=True, comment='最高连板数'),
        sa.Column('status', sa.String(20), nullable=False, server_default='success', comment='状态'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='失败原因'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trade_date', name='uix_market_pulse_date'),
    )


def downgrade() -> None:
    op.drop_table('market_pulse')
