"""add_ai_morning_reports

Revision ID: b25892702575
Revises: 998f1a99546c
Create Date: 2026-07-12 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b25892702575'
down_revision: Union[str, None] = '998f1a99546c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS ai_morning_reports (
                id SERIAL PRIMARY KEY,
                report_date DATE NOT NULL,
                content TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uix_ai_morning_report_date UNIQUE (report_date)
            )
            """
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_ai_morning_reports_report_date ON ai_morning_reports(report_date)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS ai_morning_reports CASCADE"))
