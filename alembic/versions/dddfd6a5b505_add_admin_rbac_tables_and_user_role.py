"""add_admin_rbac_tables_and_user_role

Revision ID: dddfd6a5b505
Revises: d7d13bbbbba6
Create Date: 2026-07-09 21:18:40.949599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dddfd6a5b505'
down_revision: Union[str, None] = 'd7d13bbbbba6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 新建 RBAC 表
    op.create_table('admin_menus',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('parent_id', sa.Integer(), server_default='0', nullable=False, comment='父菜单 ID，0 表示顶级'),
    sa.Column('path', sa.String(length=255), nullable=False, comment='路由路径'),
    sa.Column('name', sa.String(length=100), nullable=True, comment='路由 name（唯一标识）'),
    sa.Column('component', sa.String(length=255), nullable=True, comment='前端组件路径'),
    sa.Column('redirect', sa.String(length=255), nullable=True, comment='重定向地址'),
    sa.Column('title', sa.String(length=100), nullable=False, comment='菜单标题'),
    sa.Column('icon', sa.String(length=100), nullable=True, comment='菜单图标'),
    sa.Column('menu_type', sa.Integer(), server_default='1', nullable=False, comment='类型: 0=目录 1=菜单 2=按钮'),
    sa.Column('rank', sa.Integer(), server_default='0', nullable=False, comment='排序（越小越靠前）'),
    sa.Column('show_link', sa.Integer(), server_default='1', nullable=False, comment='是否显示: 1=是 0=否'),
    sa.Column('keep_alive', sa.Integer(), server_default='0', nullable=False, comment='是否缓存: 1=是 0=否'),
    sa.Column('extra_meta', sa.Text(), nullable=True, comment='额外 meta 配置（JSON）'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('admin_permissions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('menu_id', sa.Integer(), nullable=False, comment='所属菜单 ID'),
    sa.Column('code', sa.String(length=100), nullable=False, comment='权限标识，如 system:user:add'),
    sa.Column('name', sa.String(length=100), nullable=False, comment='权限名称'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('role_menus',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False, comment='角色标识: admin / user'),
    sa.Column('menu_id', sa.Integer(), nullable=False, comment='菜单 ID'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('role_permissions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False, comment='角色标识: admin / user'),
    sa.Column('permission_id', sa.Integer(), nullable=False, comment='权限 ID'),
    sa.PrimaryKeyConstraint('id')
    )

    # users 表新增字段
    op.add_column('users', sa.Column('avatar', sa.String(length=500), nullable=True, comment='头像 URL'))
    op.add_column('users', sa.Column('role', sa.String(length=20), server_default='user', nullable=False, comment='角色: admin / user'))
    op.add_column('users', sa.Column('is_active', sa.Integer(), server_default='1', nullable=False, comment='是否启用: 1=是 0=否'))


def downgrade() -> None:
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'role')
    op.drop_column('users', 'avatar')
    op.drop_table('role_permissions')
    op.drop_table('role_menus')
    op.drop_table('admin_permissions')
    op.drop_table('admin_menus')
