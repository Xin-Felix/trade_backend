"""add provider column to data_sources table

Revision ID: a1b2c3d4e5f6
Revises: dddfd6a5b505
Create Date: 2026-07-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dddfd6a5b505'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 provider 列（默认值 tushare，兼容存量数据）
    op.add_column(
        'data_sources',
        sa.Column('provider', sa.String(20), nullable=False, server_default='tushare', comment='数据源提供商: tushare/akshare/custom')
    )

    # 2. 扩展 api_name 长度 50 -> 80（akshare 函数名较长）
    op.alter_column(
        'data_sources',
        'api_name',
        existing_type=sa.String(50),
        type_=sa.String(80),
        existing_nullable=False,
    )

    # 3. 移除旧的 api_name 唯一约束
    #    注意：旧约束可能是 data_sources_api_name_key（PostgreSQL 自动命名）
    op.drop_constraint('data_sources_api_name_key', 'data_sources', type_='unique')

    # 4. 创建新的 (provider, api_name) 联合唯一索引
    op.create_index('uix_provider_api_name', 'data_sources', ['provider', 'api_name'], unique=True)

    # 5. 给存量记录设置 provider = 'tushare'
    op.execute("UPDATE data_sources SET provider = 'tushare' WHERE provider IS NULL OR provider = ''")


def downgrade() -> None:
    # 1. 移除联合唯一索引
    op.drop_index('uix_provider_api_name', table_name='data_sources')

    # 2. 恢复 api_name 唯一约束
    op.create_unique_constraint('data_sources_api_name_key', 'data_sources', ['api_name'])

    # 3. 恢复 api_name 长度
    op.alter_column(
        'data_sources',
        'api_name',
        existing_type=sa.String(80),
        type_=sa.String(50),
        existing_nullable=False,
    )

    # 4. 移除 provider 列
    op.drop_column('data_sources', 'provider')
