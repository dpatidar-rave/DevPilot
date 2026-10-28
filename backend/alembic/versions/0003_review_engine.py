"""Review configuration and grounded findings.

Revision ID: 0003_review_engine
Revises: 0002_selections
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_review_engine"
down_revision: str | None = "0002_selections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("reviews", sa.Column("max_output_tokens", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("timeout_seconds", sa.Float(), nullable=True))
    op.add_column("reviews", sa.Column("keep_alive", sa.String(length=16), nullable=True))
    op.add_column(
        "reviews",
        sa.Column("files_reviewed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("files_skipped", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("chunks_total", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("chunks_completed", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("reviews", sa.Column("summary", sa.Text(), server_default="", nullable=False))
    op.add_column(
        "reviews",
        sa.Column("limitations_json", sa.Text(), server_default="[]", nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("skipped_json", sa.Text(), server_default="[]", nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("reviewed_json", sa.Text(), server_default="[]", nullable=False),
    )
    op.add_column(
        "review_findings",
        sa.Column("evidence", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "review_findings",
        sa.Column("remediation", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "review_findings",
        sa.Column("verification", sa.String(length=32), server_default="needs_review", nullable=False),
    )
    op.add_column(
        "review_findings",
        sa.Column("stable_key", sa.String(length=64), server_default="", nullable=False),
    )
    op.add_column(
        "review_findings",
        sa.Column("scope", sa.String(length=32), server_default="", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("review_findings", "scope")
    op.drop_column("review_findings", "stable_key")
    op.drop_column("review_findings", "verification")
    op.drop_column("review_findings", "remediation")
    op.drop_column("review_findings", "evidence")
    op.drop_column("reviews", "reviewed_json")
    op.drop_column("reviews", "skipped_json")
    op.drop_column("reviews", "limitations_json")
    op.drop_column("reviews", "summary")
    op.drop_column("reviews", "chunks_completed")
    op.drop_column("reviews", "chunks_total")
    op.drop_column("reviews", "files_skipped")
    op.drop_column("reviews", "files_reviewed")
    op.drop_column("reviews", "keep_alive")
    op.drop_column("reviews", "timeout_seconds")
    op.drop_column("reviews", "max_output_tokens")
    op.drop_column("reviews", "temperature")
