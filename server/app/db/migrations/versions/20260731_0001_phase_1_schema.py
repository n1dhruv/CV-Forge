"""Create the complete ResumeForge schema."""

from alembic import op

revision = "20260731_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute(
        """
    CREATE TABLE users (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), clerk_user_id text UNIQUE NOT NULL, email text NOT NULL, first_name text, last_name text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE skill_bank_items (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, type text NOT NULL CONSTRAINT skill_bank_items_type_check CHECK (type IN ('experience','project','skill','education','certification')), title text NOT NULL, org text, start_date date, end_date date, raw_text text, tags text[] DEFAULT '{}', embedding vector(1536), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE bullet_points (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), item_id uuid NOT NULL REFERENCES skill_bank_items(id) ON DELETE CASCADE, text text NOT NULL, tags text[] DEFAULT '{}', metrics text, embedding vector(1536), display_order int NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE job_descriptions (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, raw_text text NOT NULL, source_file_url text, parsed_json jsonb, status text NOT NULL DEFAULT 'queued' CONSTRAINT job_descriptions_status_check CHECK (status IN ('queued','running','done','failed')), created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE jd_requirements (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), jd_id uuid NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE, skill text NOT NULL, importance text NOT NULL CONSTRAINT jd_requirements_importance_check CHECK (importance IN ('required','nice_to_have')), category text);
    CREATE TABLE resume_versions (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, jd_id uuid REFERENCES job_descriptions(id) ON DELETE SET NULL, tex_source text NOT NULL, pdf_storage_path text, ats_score numeric, parent_version_id uuid REFERENCES resume_versions(id), created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE resume_bullet_selections (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), resume_version_id uuid NOT NULL REFERENCES resume_versions(id) ON DELETE CASCADE, bullet_point_id uuid NOT NULL REFERENCES bullet_points(id) ON DELETE CASCADE, original_text text NOT NULL, rewritten_text text, approved boolean NOT NULL DEFAULT false, section_order int NOT NULL DEFAULT 0);
    CREATE TABLE github_repos (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, repo_name text NOT NULL, repo_url text NOT NULL, languages jsonb, readme_summary text, inferred_skills text[] DEFAULT '{}', last_synced_at timestamptz, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE leetcode_stats (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, topic text NOT NULL, solved_count int NOT NULL DEFAULT 0, difficulty_distribution jsonb, last_synced_at timestamptz);
    CREATE TABLE background_jobs (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, job_type text NOT NULL, status text NOT NULL DEFAULT 'queued' CONSTRAINT background_jobs_status_check CHECK (status IN ('queued','running','done','failed')), result jsonb, error text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
    CREATE INDEX skill_bank_items_embedding_idx ON skill_bank_items USING ivfflat (embedding vector_cosine_ops);
    CREATE INDEX bullet_points_embedding_idx ON bullet_points USING ivfflat (embedding vector_cosine_ops);
    CREATE INDEX skill_bank_items_user_id_idx ON skill_bank_items (user_id);
    CREATE INDEX bullet_points_item_id_idx ON bullet_points (item_id);
    CREATE INDEX job_descriptions_user_id_idx ON job_descriptions (user_id);
    CREATE INDEX resume_versions_user_id_idx ON resume_versions (user_id);
    CREATE INDEX background_jobs_user_id_status_idx ON background_jobs (user_id, status);
    """
    )


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS background_jobs, leetcode_stats, github_repos, resume_bullet_selections, resume_versions, jd_requirements, job_descriptions, bullet_points, skill_bank_items, users CASCADE"
    )
