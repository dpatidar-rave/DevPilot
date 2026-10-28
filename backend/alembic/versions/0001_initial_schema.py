"""Initial local schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("path", name="uq_projects_path"),
    )
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("base_ref", sa.String(length=200), nullable=True),
        sa.Column("head_ref", sa.String(length=200), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("finding_count", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_reviews_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_reviews_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reviews"),
    )
    op.create_index("ix_reviews_project_id", "reviews", ["project_id"])
    op.create_table(
        "review_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("uncertain", sa.Boolean(), nullable=False),
        sa.Column(
            "validation_status",
            sa.String(length=32),
            server_default="uncertain",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_review_findings_severity",
        ),
        sa.CheckConstraint(
            "validation_status IN ('accepted', 'rejected', 'uncertain')",
            name="ck_review_findings_validation_status",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_review_findings_confidence",
        ),
        sa.CheckConstraint("start_line >= 1", name="ck_review_findings_start_line"),
        sa.CheckConstraint("end_line >= start_line", name="ck_review_findings_line_range"),
        sa.CheckConstraint(
            "(confidence >= 0.5) OR (uncertain = 1)",
            name="ck_review_findings_uncertain",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name="fk_review_findings_review_id_reviews",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_review_findings"),
    )
    op.create_index("ix_review_findings_review_id", "review_findings", ["review_id"])
    op.create_table(
        "quality_check_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_quality_check_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_quality_check_runs_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name="fk_quality_check_runs_review_id_reviews",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quality_check_runs"),
    )
    op.create_index("ix_quality_check_runs_project_id", "quality_check_runs", ["project_id"])
    op.create_table(
        "release_reports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'archived')",
            name="ck_release_reports_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_release_reports_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name="fk_release_reports_review_id_reviews",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_release_reports"),
    )
    op.create_index("ix_release_reports_project_id", "release_reports", ["project_id"])
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_app_settings"),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index("ix_release_reports_project_id", table_name="release_reports")
    op.drop_table("release_reports")
    op.drop_index("ix_quality_check_runs_project_id", table_name="quality_check_runs")
    op.drop_table("quality_check_runs")
    op.drop_index("ix_review_findings_review_id", table_name="review_findings")
    op.drop_table("review_findings")
    op.drop_index("ix_reviews_project_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_table("projects")
