"""Add per-user LLM settings and allow queued PDF JDs without extracted text."""

from alembic import op

revision = "20260804_0002"
down_revision = "20260731_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE user_llm_settings ("
        "id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), "
        "user_id uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, "
        "provider text NOT NULL, model text NOT NULL, encrypted_api_key text NOT NULL, "
        "created_at timestamptz NOT NULL DEFAULT now(), "
        "updated_at timestamptz NOT NULL DEFAULT now())"
    )
    op.execute("ALTER TABLE user_llm_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE job_descriptions ALTER COLUMN raw_text DROP NOT NULL")


def downgrade() -> None:
    op.execute("UPDATE job_descriptions SET raw_text = '' WHERE raw_text IS NULL")
    op.execute("ALTER TABLE job_descriptions ALTER COLUMN raw_text SET NOT NULL")
    op.execute("DROP TABLE user_llm_settings")
