"""add_soft_delete_to_user_tables

Revision ID: 95e317eb8509
Revises: 6fa4fe62d3a8
Create Date: 2026-07-12 22:25:35.911314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95e317eb8509'
down_revision: Union[str, None] = '6fa4fe62d3a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为用户相关表添加软删除标记字段及索引
    tables = [
        'users',
        'verification_codes',
        'watchlist',
        'portfolio',
        'daily_reviews',
        'ai_position_advices',
        'user_points',
        'point_records',
        'user_memberships',
        'subscription_orders',
        'user_feature_usage',
    ]
    for table in tables:
        op.add_column(
            table,
            sa.Column(
                'is_deleted',
                sa.Integer(),
                server_default='0',
                nullable=False,
                comment='是否已删除: 0=否 1=是',
            ),
        )
        op.create_index(
            op.f(f'ix_{table}_is_deleted'),
            table,
            ['is_deleted'],
            unique=False,
        )


def downgrade() -> None:
    tables = [
        'user_feature_usage',
        'subscription_orders',
        'user_memberships',
        'point_records',
        'user_points',
        'ai_position_advices',
        'daily_reviews',
        'portfolio',
        'watchlist',
        'verification_codes',
        'users',
    ]
    for table in tables:
        op.drop_index(op.f(f'ix_{table}_is_deleted'), table_name=table)
        op.drop_column(table, 'is_deleted')
