"""Create the local reviews table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("repository_path", sa.String(length=4096), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_reviews_created_at", "reviews", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_reviews_created_at", table_name="reviews")
    op.drop_table("reviews")
