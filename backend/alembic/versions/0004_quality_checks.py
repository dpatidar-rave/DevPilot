"""Per-repository quality commands and stored check results.

Revision ID: 0004_quality_checks
Revises: 0003_review_engine
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_quality_checks"
down_revision: str | None = "0003_review_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quality_commands",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("tool", sa.String(length=32), nullable=False),
        sa.Column("argv_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tool IN ('phpcs', 'phpstan', 'phpunit', 'composer', 'magento')",
            name="ck_quality_commands_tool",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_quality_commands_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "tool", name="pk_quality_commands"),
    )
    op.create_index(
        "ix_quality_commands_project_id",
        "quality_commands",
        ["project_id"],
    )
    op.add_column("quality_check_runs", sa.Column("tool", sa.String(length=32), nullable=True))
    op.add_column("quality_check_runs", sa.Column("argv_json", sa.Text(), nullable=True))
    op.add_column("quality_check_runs", sa.Column("command_display", sa.Text(), nullable=True))
    op.add_column(
        "quality_check_runs",
        sa.Column("working_directory", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "quality_check_runs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quality_check_runs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("quality_check_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("quality_check_runs", sa.Column("exit_code", sa.Integer(), nullable=True))
    op.add_column("quality_check_runs", sa.Column("result", sa.String(length=16), nullable=True))
    op.add_column("quality_check_runs", sa.Column("stdout", sa.Text(), nullable=True))
    op.add_column("quality_check_runs", sa.Column("stderr", sa.Text(), nullable=True))
    op.add_column(
        "quality_check_runs",
        sa.Column("output_truncated", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("quality_check_runs", "output_truncated")
    op.drop_column("quality_check_runs", "stderr")
    op.drop_column("quality_check_runs", "stdout")
    op.drop_column("quality_check_runs", "result")
    op.drop_column("quality_check_runs", "exit_code")
    op.drop_column("quality_check_runs", "duration_ms")
    op.drop_column("quality_check_runs", "finished_at")
    op.drop_column("quality_check_runs", "started_at")
    op.drop_column("quality_check_runs", "working_directory")
    op.drop_column("quality_check_runs", "command_display")
    op.drop_column("quality_check_runs", "argv_json")
    op.drop_column("quality_check_runs", "tool")
    op.drop_index("ix_quality_commands_project_id", table_name="quality_commands")
    op.drop_table("quality_commands")
