"""make_unique_constraints_partial_for_soft_delete

Revision ID: 508bb60727b2
Revises: 82c6daf1bd1d
Create Date: 2026-07-12 14:56:29.305219

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '508bb60727b2'
down_revision: Union[str, None] = '82c6daf1bd1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_partial_unique_index(table: str, name: str, columns: list[str]) -> None:
    """创建仅对未删除记录生效的部分唯一索引，并删除旧的普通唯一约束。"""
    op.drop_constraint(name, table, type_='unique')
    op.create_index(
        f'{name}_active',
        table,
        columns,
        unique=True,
        postgresql_where='is_deleted = 0',
    )


def _restore_unique_constraint(table: str, name: str, columns: list[str]) -> None:
    """降级：删除部分唯一索引，恢复普通唯一约束。"""
    op.drop_index(f'{name}_active', table_name=table, postgresql_where='is_deleted = 0')
    op.create_unique_constraint(name, table, columns)


def upgrade() -> None:
    _create_partial_unique_index(
        'ai_position_advices',
        'uix_ai_position_advice_user_date',
        ['user_id', 'report_date'],
    )
    _create_partial_unique_index(
        'daily_reviews',
        'uix_daily_review_user_date_level',
        ['user_id', 'report_date', 'level'],
    )
    _create_partial_unique_index(
        'portfolio',
        'uq_portfolio_user_code',
        ['user_id', 'ts_code'],
    )
    _create_partial_unique_index(
        'user_feature_usage',
        'uix_user_feature_usage',
        ['user_id', 'feature_code', 'usage_date'],
    )
    _create_partial_unique_index(
        'watchlist',
        'uq_watchlist_user_code',
        ['user_id', 'ts_code'],
    )


def downgrade() -> None:
    _restore_unique_constraint(
        'watchlist',
        'uq_watchlist_user_code',
        ['user_id', 'ts_code'],
    )
    _restore_unique_constraint(
        'user_feature_usage',
        'uix_user_feature_usage',
        ['user_id', 'feature_code', 'usage_date'],
    )
    _restore_unique_constraint(
        'portfolio',
        'uq_portfolio_user_code',
        ['user_id', 'ts_code'],
    )
    _restore_unique_constraint(
        'daily_reviews',
        'uix_daily_review_user_date_level',
        ['user_id', 'report_date', 'level'],
    )
    _restore_unique_constraint(
        'ai_position_advices',
        'uix_ai_position_advice_user_date',
        ['user_id', 'report_date'],
    )
