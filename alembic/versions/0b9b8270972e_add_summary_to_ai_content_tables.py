"""add_summary_to_ai_content_tables

Revision ID: 0b9b8270972e
Revises: 508bb60727b2
Create Date: 2026-07-12 23:58:59.317268

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b9b8270972e'
down_revision: Union[str, None] = '508bb60727b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "daily_reviews",
        sa.Column("summary", sa.Text(), nullable=True, comment="AI 生成的复盘摘要（1-2句话，100字以内）"),
    )
    op.add_column(
        "ai_position_advices",
        sa.Column("summary", sa.Text(), nullable=True, comment="AI 生成的仓位建议摘要（1-2句话，100字以内）"),
    )
    op.add_column(
        "ai_morning_reports",
        sa.Column("summary", sa.Text(), nullable=True, comment="AI 生成的晨报摘要（1-2句话，100字以内）"),
    )


def downgrade() -> None:
    op.drop_column("daily_reviews", "summary")
    op.drop_column("ai_position_advices", "summary")
    op.drop_column("ai_morning_reports", "summary")
