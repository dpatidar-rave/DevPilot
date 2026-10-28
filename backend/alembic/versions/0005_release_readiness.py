"""Release readiness snapshots and human dispositions.

Revision ID: 0005_release_readiness
Revises: 0004_quality_checks
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_release_readiness"
down_revision: str | None = "0004_quality_checks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("release_reports", sa.Column("readiness", sa.String(length=32), nullable=True))
    op.add_column("release_reports", sa.Column("base_ref", sa.String(length=200), nullable=True))
    op.add_column("release_reports", sa.Column("head_sha", sa.String(length=64), nullable=True))
    op.add_column(
        "release_reports",
        sa.Column("repository_head_sha", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "release_reports",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("release_reports", sa.Column("model_name", sa.String(length=128), nullable=True))
    op.add_column("release_reports", sa.Column("report_json", sa.Text(), nullable=True))
    op.add_column("release_reports", sa.Column("report_markdown", sa.Text(), nullable=True))
    op.create_table(
        "finding_decisions",
        sa.Column("finding_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("reviewer_label", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('dismissed', 'confirmed', 'waived')",
            name="ck_finding_decisions_decision",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id"],
            ["review_findings.id"],
            name="fk_finding_decisions_finding_id_review_findings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("finding_id", name="pk_finding_decisions"),
    )
    op.create_table(
        "release_checklist_decisions",
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("item_key", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("reviewer_label", sa.String(length=80), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'waived', 'not_applicable')",
            name="ck_release_checklist_decisions_status",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name="fk_release_checklist_decisions_review_id_reviews",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_release_checklist_decisions_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("review_id", "item_key", name="pk_release_checklist_decisions"),
    )
    op.create_index(
        "ix_release_checklist_decisions_project_id",
        "release_checklist_decisions",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_release_checklist_decisions_project_id",
        table_name="release_checklist_decisions",
    )
    op.drop_table("release_checklist_decisions")
    op.drop_table("finding_decisions")
    op.drop_column("release_reports", "report_markdown")
    op.drop_column("release_reports", "report_json")
    op.drop_column("release_reports", "model_name")
    op.drop_column("release_reports", "generated_at")
    op.drop_column("release_reports", "repository_head_sha")
    op.drop_column("release_reports", "head_sha")
    op.drop_column("release_reports", "base_ref")
    op.drop_column("release_reports", "readiness")
