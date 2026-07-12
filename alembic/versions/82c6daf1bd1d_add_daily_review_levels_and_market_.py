"""add daily review levels and market daily review

Revision ID: 82c6daf1bd1d
Revises: 95e317eb8509
Create Date: 2026-07-12 22:42:35.018608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82c6daf1bd1d'
down_revision: Union[str, None] = '95e317eb8509'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 为 daily_reviews 增加 level 和 prompt_version 字段
    op.add_column(
        "daily_reviews",
        sa.Column("level", sa.String(20), server_default="standard", nullable=False),
    )
    op.add_column(
        "daily_reviews",
        sa.Column("prompt_version", sa.String(20), nullable=True),
    )

    # 2. 更新现有记录的 level 为 standard
    op.execute(sa.text("UPDATE daily_reviews SET level = 'standard' WHERE level IS NULL"))

    # 3. 删除旧的唯一约束，创建新的包含 level 的唯一约束
    op.execute(
        sa.text(
            "ALTER TABLE daily_reviews DROP CONSTRAINT IF EXISTS uix_daily_review_user_date"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE daily_reviews ADD CONSTRAINT uix_daily_review_user_date_level UNIQUE (user_id, report_date, level)"
        )
    )

    # 4. 创建 market_daily_reviews 表
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS market_daily_reviews (
                id SERIAL PRIMARY KEY,
                report_date DATE NOT NULL UNIQUE,
                level VARCHAR(20) NOT NULL DEFAULT 'brief',
                content TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                prompt_version VARCHAR(20),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_market_daily_reviews_report_date ON market_daily_reviews(report_date)"
        )
    )


def downgrade() -> None:
    # 1. 删除 market_daily_reviews 表
    op.execute(sa.text("DROP TABLE IF EXISTS market_daily_reviews CASCADE"))

    # 2. 恢复 daily_reviews 唯一约束
    op.execute(
        sa.text(
            "ALTER TABLE daily_reviews DROP CONSTRAINT IF EXISTS uix_daily_review_user_date_level"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE daily_reviews ADD CONSTRAINT uix_daily_review_user_date UNIQUE (user_id, report_date)"
        )
    )

    # 3. 删除新增字段
    op.drop_column("daily_reviews", "level")
    op.drop_column("daily_reviews", "prompt_version")
