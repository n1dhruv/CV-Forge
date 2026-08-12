"""Add resume rewriting lifecycle and review metadata."""

from alembic import op

revision = "20260810_0007"
down_revision = "20260808_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE resume_versions ALTER COLUMN tex_source DROP NOT NULL")
    op.execute("ALTER TABLE resume_versions ADD COLUMN status text NOT NULL DEFAULT 'draft'")
    op.execute(
        "ALTER TABLE resume_versions ADD CONSTRAINT resume_versions_status_check "
        "CHECK (status IN ('draft','rewriting','reviewing','finalized'))"
    )
    op.execute(
        "ALTER TABLE resume_bullet_selections ADD COLUMN flagged_terms jsonb "
        "NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE resume_bullet_selections ADD COLUMN resolved boolean " "NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE resume_bullet_selections ADD CONSTRAINT "
        "resume_bullet_selections_version_bullet_key "
        "UNIQUE (resume_version_id, bullet_point_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE resume_bullet_selections DROP CONSTRAINT "
        "resume_bullet_selections_version_bullet_key"
    )
    op.execute("ALTER TABLE resume_bullet_selections DROP COLUMN resolved")
    op.execute("ALTER TABLE resume_bullet_selections DROP COLUMN flagged_terms")
    op.execute("ALTER TABLE resume_versions DROP CONSTRAINT resume_versions_status_check")
    op.execute("ALTER TABLE resume_versions DROP COLUMN status")
    op.execute("UPDATE resume_versions SET tex_source = '' WHERE tex_source IS NULL")
    op.execute("ALTER TABLE resume_versions ALTER COLUMN tex_source SET NOT NULL")
