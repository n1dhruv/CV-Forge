"""Add resume profile fields and selected skills."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260814_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in (
        "full_name",
        "contact_email",
        "phone",
        "location",
        "linkedin_url",
        "github_url",
        "leetcode_url",
        "portfolio_url",
    ):
        op.add_column("users", sa.Column(name, sa.Text(), nullable=True))
    op.add_column("skill_bank_items", sa.Column("skill_category", sa.Text(), nullable=True))
    op.add_column(
        "resume_versions",
        sa.Column(
            "selected_skills",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("resume_versions", "selected_skills")
    op.drop_column("skill_bank_items", "skill_category")
    for name in (
        "portfolio_url",
        "leetcode_url",
        "github_url",
        "linkedin_url",
        "location",
        "phone",
        "contact_email",
        "full_name",
    ):
        op.drop_column("users", name)
