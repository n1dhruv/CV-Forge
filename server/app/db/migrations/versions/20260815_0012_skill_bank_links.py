"""Add optional named links to projects and certifications."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260815_0012"
down_revision = "20260814_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "skill_bank_items",
        sa.Column(
            "links",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "skill_bank_items_links_check",
        "skill_bank_items",
        "jsonb_typeof(links) = 'array' AND jsonb_array_length(links) <= 2 AND ("
        "type = 'project' OR "
        "type = 'certification' AND jsonb_array_length(links) <= 1 OR "
        "type NOT IN ('project','certification') AND links = '[]'::jsonb)",
    )


def downgrade() -> None:
    op.drop_constraint("skill_bank_items_links_check", "skill_bank_items", type_="check")
    op.drop_column("skill_bank_items", "links")
