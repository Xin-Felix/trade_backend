"""add_sector_default_configs

Revision ID: c7e8d9f0a1b2
Revises: 460d4f74dbce
Create Date: 2026-07-14 20:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e8d9f0a1b2'
down_revision: Union[str, None] = '460d4f74dbce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sector_default_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sector_type', sa.String(50), nullable=False, comment='板块类型: concept=概念, industry=行业'),
        sa.Column('sector_ids', sa.JSON(), nullable=False, server_default='[]', comment='默认勾选的板块/概念ID列表'),
        sa.Column('is_enabled', sa.Integer(), nullable=False, server_default='1', comment='是否启用: 1=是 0=否'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sector_type', name='uix_sector_default_configs_type'),
    )


def downgrade() -> None:
    op.drop_table('sector_default_configs')
