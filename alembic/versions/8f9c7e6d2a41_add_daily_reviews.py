"""add_daily_reviews

Revision ID: 8f9c7e6d2a41
Revises: 5e28c7eda501
Create Date: 2026-07-12 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f9c7e6d2a41'
down_revision: Union[str, None] = '5e28c7eda501'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS daily_reviews (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                report_date DATE NOT NULL,
                content TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uix_daily_review_user_date UNIQUE (user_id, report_date),
                CONSTRAINT fk_daily_reviews_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_daily_reviews_user_id ON daily_reviews(user_id)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS daily_reviews CASCADE"))
