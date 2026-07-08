"""add verification_codes and make user password nullable

Revision ID: 2f8f3f9f8b3a
Revises: 57fdd518cbc3
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "2f8f3f9f8b3a"
down_revision: Union[str, None] = "57fdd518cbc3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "hashed_password",
                     existing_type=mysql.VARCHAR(length=255),
                     nullable=True)
    op.create_table(
        "verification_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_verification_codes_email"), "verification_codes", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_verification_codes_email"), table_name="verification_codes")
    op.drop_table("verification_codes")
    op.alter_column("users", "hashed_password",
                     existing_type=mysql.VARCHAR(length=255),
                     nullable=False)
