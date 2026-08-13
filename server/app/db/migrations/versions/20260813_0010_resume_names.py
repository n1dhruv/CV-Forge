"""Add resume family and version names."""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0010"
down_revision = "20260812_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "resume_versions",
        sa.Column("name", sa.Text(), nullable=False, server_default="Resume"),
    )
    op.add_column(
        "resume_versions",
        sa.Column("version_label", sa.Text(), nullable=False, server_default="Initial"),
    )


def downgrade() -> None:
    op.drop_column("resume_versions", "version_label")
    op.drop_column("resume_versions", "name")
