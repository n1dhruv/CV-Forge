"""Add LaTeX assembly and compilation lifecycle states."""

from alembic import op

revision = "20260812_0009"
down_revision = "20260810_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE resume_versions DROP CONSTRAINT resume_versions_status_check")
    op.execute(
        "ALTER TABLE resume_versions ADD CONSTRAINT resume_versions_status_check "
        "CHECK (status IN ('draft','rewriting','reviewing','finalized','assembling',"
        "'assembled','compiling','compiled','compile_failed'))"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE resume_versions SET status = 'finalized' "
        "WHERE status IN ('assembling','assembled','compiling','compiled','compile_failed')"
    )
    op.execute("ALTER TABLE resume_versions DROP CONSTRAINT resume_versions_status_check")
    op.execute(
        "ALTER TABLE resume_versions ADD CONSTRAINT resume_versions_status_check "
        "CHECK (status IN ('draft','rewriting','reviewing','finalized'))"
    )
