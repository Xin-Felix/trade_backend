"""add stock moneyflow index top ths tables

Revision ID: d7d13bbbbba6
Revises: 2f8f3f9f8b3a
Create Date: 2026-07-08 14:04:08.660428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7d13bbbbba6'
down_revision: Union[str, None] = '2f8f3f9f8b3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 统一 numeric 精度为 Numeric(20, 4)
    op.alter_column('stock_daily', 'pct_chg',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='涨跌幅',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'turnover_rate',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='换手率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'turnover_rate_f',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='换手率（自由流通股）',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'volume_ratio',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='量比',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pe',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='市盈率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pe_ttm',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='市盈率 TTM',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pb',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='市净率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='市销率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'ps_ttm',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='市销率 TTM',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'dv_ratio',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='股息率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'dv_ttm',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='股息率 TTM',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'eps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='基本每股收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'dt_eps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='稀释每股收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'total_revenue_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='营业总收入每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'revenue_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='营业收入每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'capital_rese_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='资本公积每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'surplus_rese_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='盈余公积每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'undist_profit_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='未分配利润每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'diluted2_eps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='期末摊薄每股收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'bps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股净资产',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'ocfps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股经营活动产生的现金流量净额',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'retainedps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股留存收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'cfps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股现金流量净额',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'ebit_ps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股息税前利润',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'fcfps',
               existing_type=sa.NUMERIC(precision=14, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_comment='每股企业自由现金流量',
               existing_nullable=True)
    op.alter_column('stock_monthly', 'pct_chg',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_nullable=True)
    op.alter_column('stock_weekly', 'pct_chg',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_nullable=True)
    op.alter_column('stock_yearly', 'pct_chg',
               existing_type=sa.NUMERIC(precision=10, scale=4),
               type_=sa.Numeric(precision=20, scale=4),
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('stock_yearly', 'pct_chg',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_nullable=True)
    op.alter_column('stock_weekly', 'pct_chg',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_nullable=True)
    op.alter_column('stock_monthly', 'pct_chg',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'fcfps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股企业自由现金流量',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'ebit_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股息税前利润',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'cfps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股现金流量净额',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'retainedps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股留存收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'ocfps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股经营活动产生的现金流量净额',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'bps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='每股净资产',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'diluted2_eps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='期末摊薄每股收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'undist_profit_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='未分配利润每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'surplus_rese_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='盈余公积每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'capital_rese_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='资本公积每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'revenue_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='营业收入每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'total_revenue_ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='营业总收入每股',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'dt_eps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='稀释每股收益',
               existing_nullable=True)
    op.alter_column('stock_fina_indicator', 'eps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='基本每股收益',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'dv_ttm',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='股息率 TTM',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'dv_ratio',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='股息率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'ps_ttm',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='市销率 TTM',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'ps',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='市销率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pb',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='市净率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pe_ttm',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='市盈率 TTM',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'pe',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=14, scale=4),
               existing_comment='市盈率',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'volume_ratio',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='量比',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'turnover_rate_f',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='换手率（自由流通股）',
               existing_nullable=True)
    op.alter_column('stock_daily_basic', 'turnover_rate',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='换手率',
               existing_nullable=True)
    op.alter_column('stock_daily', 'pct_chg',
               existing_type=sa.Numeric(precision=20, scale=4),
               type_=sa.NUMERIC(precision=10, scale=4),
               existing_comment='涨跌幅',
               existing_nullable=True)
