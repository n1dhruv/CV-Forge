"""Move embeddings to Pinecone and add Phase 3 matching/import schema."""

from alembic import op

revision = "20260806_0005"
down_revision = "20260806_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.skill_bank_items_embedding_idx")
    op.execute("DROP INDEX IF EXISTS public.bullet_points_embedding_idx")
    op.execute("ALTER TABLE public.skill_bank_items DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE public.bullet_points DROP COLUMN IF EXISTS embedding")
    op.execute(
        "ALTER TABLE public.user_llm_settings "
        "ADD COLUMN embedding_provider text, "
        "ADD COLUMN embedding_model text, "
        "ADD COLUMN encrypted_embedding_api_key text"
    )
    op.execute(
        "CREATE TABLE public.jd_action_verbs ("
        "id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), "
        "jd_id uuid NOT NULL REFERENCES public.job_descriptions(id) ON DELETE CASCADE, "
        "verb text NOT NULL)"
    )
    op.execute("CREATE INDEX jd_action_verbs_jd_id_idx ON public.jd_action_verbs (jd_id)")
    op.execute(
        "CREATE TABLE public.resume_imports ("
        "id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), "
        "user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE, "
        "source_file_url text, raw_text text, parsed_json jsonb, "
        "status text NOT NULL DEFAULT 'queued' "
        "CONSTRAINT resume_imports_status_check "
        "CHECK (status IN ('queued','running','done','failed')), "
        "created_at timestamptz NOT NULL DEFAULT now(), committed_at timestamptz)"
    )
    op.execute("CREATE INDEX resume_imports_user_id_idx ON public.resume_imports (user_id)")
    op.execute(
        "ALTER TABLE public.skill_bank_items ADD COLUMN source text NOT NULL DEFAULT 'manual' "
        "CONSTRAINT skill_bank_items_source_check "
        "CHECK (source IN ('manual','resume_import','github'))"
    )
    for table in ("jd_action_verbs", "resume_imports"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM anon, authenticated")


def downgrade() -> None:
    op.execute("ALTER TABLE public.skill_bank_items DROP COLUMN source")
    op.execute("DROP TABLE public.resume_imports")
    op.execute("DROP TABLE public.jd_action_verbs")
    op.execute(
        "ALTER TABLE public.user_llm_settings "
        "DROP COLUMN encrypted_embedding_api_key, "
        "DROP COLUMN embedding_model, DROP COLUMN embedding_provider"
    )
    op.execute("ALTER TABLE public.skill_bank_items ADD COLUMN embedding vector(1536)")
    op.execute("ALTER TABLE public.bullet_points ADD COLUMN embedding vector(1536)")
    op.execute(
        "CREATE INDEX skill_bank_items_embedding_idx ON public.skill_bank_items "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX bullet_points_embedding_idx ON public.bullet_points "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
