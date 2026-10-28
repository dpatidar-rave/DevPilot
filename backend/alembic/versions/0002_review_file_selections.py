"""Store the files selected for a later review.

Revision ID: 0002_selections
Revises: 0001_initial
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_selections"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_file_selections",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_review_file_selections_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "path", name="pk_review_file_selections"),
    )


def downgrade() -> None:
    op.drop_table("review_file_selections")
