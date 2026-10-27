"""Store schema-checked review findings.

Revision ID: 0002_findings
Revises: 0001_initial
Create Date: 2026-10-27

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_findings"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_findings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("uncertain", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_review_findings_review_id", "review_findings", ["review_id"])


def downgrade() -> None:
    op.drop_index("ix_review_findings_review_id", table_name="review_findings")
    op.drop_table("review_findings")
