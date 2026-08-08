"""Store dynamically extracted technology requirements."""

from alembic import op

revision = "20260808_0006"
down_revision = "20260806_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.jd_requirements "
        "ADD COLUMN named_technologies text[], "
        "ADD COLUMN technology_match_mode text, "
        "ADD CONSTRAINT jd_requirements_technology_match_mode_check "
        "CHECK (technology_match_mode IN ('any','all') OR technology_match_mode IS NULL)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.jd_requirements "
        "DROP CONSTRAINT jd_requirements_technology_match_mode_check, "
        "DROP COLUMN technology_match_mode, "
        "DROP COLUMN named_technologies"
    )
