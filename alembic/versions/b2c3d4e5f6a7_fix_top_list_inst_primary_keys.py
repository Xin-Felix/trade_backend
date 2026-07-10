"""fix top_list and top_inst primary keys to include reason

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ top_list: 加 reason 到主键 ============

    # 1. 先把 reason 设为 NOT NULL（主键列不能有 NULL）
    op.execute("UPDATE top_list SET reason = '' WHERE reason IS NULL")
    op.alter_column('top_list', 'reason', existing_type=sa.String(255), nullable=False, server_default='')

    # 2. 删除旧的主键和唯一约束
    # TimescaleDB hypertable 可能没有普通 pkey，尝试删除
    op.execute("""
        DO $$
        BEGIN
            -- 尝试删除 unique constraint
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_top_list') THEN
                ALTER TABLE top_list DROP CONSTRAINT uix_top_list;
            END IF;
            -- 尝试删除 primary key
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'top_list_pkey') THEN
                ALTER TABLE top_list DROP CONSTRAINT top_list_pkey;
            END IF;
        END $$;
    """)

    # 3. 创建新主键
    op.create_primary_key('top_list_pkey', 'top_list', ['trade_date', 'ts_code', 'reason'])

    # ============ top_inst: 加 reason 到主键 ============

    # 1. 把 reason 设为 NOT NULL
    op.execute("UPDATE top_inst SET reason = '' WHERE reason IS NULL")
    op.alter_column('top_inst', 'reason', existing_type=sa.String(255), nullable=False, server_default='')

    # 2. 删除旧主键
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'top_inst_pkey') THEN
                ALTER TABLE top_inst DROP CONSTRAINT top_inst_pkey;
            END IF;
        END $$;
    """)

    # 3. 创建新主键
    op.create_primary_key('top_inst_pkey', 'top_inst', ['trade_date', 'ts_code', 'exalter', 'side', 'reason'])


def downgrade() -> None:
    # top_inst: 恢复旧主键
    op.drop_constraint('top_inst_pkey', 'top_inst', type_='primary')
    op.create_primary_key('top_inst_pkey', 'top_inst', ['trade_date', 'ts_code', 'exalter', 'side'])
    op.alter_column('top_inst', 'reason', existing_type=sa.String(255), nullable=True, server_default=None)

    # top_list: 恢复旧主键
    op.drop_constraint('top_list_pkey', 'top_list', type_='primary')
    op.create_primary_key('top_list_pkey', 'top_list', ['trade_date', 'ts_code'])
    op.create_unique_constraint('uix_top_list', 'top_list', ['trade_date', 'ts_code'])
    op.alter_column('top_list', 'reason', existing_type=sa.String(255), nullable=True, server_default=None)
