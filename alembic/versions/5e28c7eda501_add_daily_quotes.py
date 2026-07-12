"""add daily_quotes

Revision ID: 5e28c7eda501
Revises: f973e8b1d2e1
Create Date: 2026-07-12 00:15:00.653559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e28c7eda501'
down_revision: Union[str, None] = 'f973e8b1d2e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS daily_quotes (
                id SERIAL PRIMARY KEY,
                content VARCHAR(500) NOT NULL,
                author VARCHAR(100),
                is_published INTEGER NOT NULL DEFAULT 1,
                display_date DATE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS daily_quotes"))
