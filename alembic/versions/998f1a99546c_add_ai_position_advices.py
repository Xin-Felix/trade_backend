"""add_ai_position_advices

Revision ID: 998f1a99546c
Revises: 0f84dc4bca24
Create Date: 2026-07-12 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '998f1a99546c'
down_revision: Union[str, None] = '0f84dc4bca24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS ai_position_advices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                report_date DATE NOT NULL,
                content TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uix_ai_position_advice_user_date UNIQUE (user_id, report_date),
                CONSTRAINT fk_ai_position_advices_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_ai_position_advices_user_id ON ai_position_advices(user_id)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS ai_position_advices CASCADE"))
