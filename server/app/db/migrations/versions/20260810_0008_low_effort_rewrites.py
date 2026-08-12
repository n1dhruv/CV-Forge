"""Persist informational low-effort rewrite flags."""

from alembic import op

revision = "20260810_0008"
down_revision = "20260810_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE resume_bullet_selections ADD COLUMN "
        "low_effort_rewrite boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE resume_bullet_selections DROP COLUMN low_effort_rewrite")
