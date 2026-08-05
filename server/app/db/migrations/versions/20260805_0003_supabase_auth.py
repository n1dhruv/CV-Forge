"""Replace Clerk identities with Supabase Auth identities."""

from alembic import op

revision = "20260805_0003"
down_revision = "20260804_0002"
branch_labels = None
depends_on = None

APPLICATION_TABLES = (
    "users",
    "skill_bank_items",
    "bullet_points",
    "job_descriptions",
    "jd_requirements",
    "resume_versions",
    "resume_bullet_selections",
    "github_repos",
    "leetcode_stats",
    "background_jobs",
    "user_llm_settings",
)

FOREIGN_KEY_INDEXES = {
    "jd_requirements_jd_id_idx": "jd_requirements (jd_id)",
    "resume_versions_jd_id_idx": "resume_versions (jd_id)",
    "resume_versions_parent_version_id_idx": "resume_versions (parent_version_id)",
    "resume_bullet_selections_resume_version_id_idx": (
        "resume_bullet_selections (resume_version_id)"
    ),
    "resume_bullet_selections_bullet_point_id_idx": ("resume_bullet_selections (bullet_point_id)"),
    "github_repos_user_id_idx": "github_repos (user_id)",
    "leetcode_stats_user_id_idx": "leetcode_stats (user_id)",
}


def upgrade() -> None:
    op.execute("ALTER TABLE public.users DROP COLUMN clerk_user_id")
    op.execute("ALTER TABLE public.users ALTER COLUMN id DROP DEFAULT")
    # ponytail: old Clerk rows remain preserved but unvalidated until manually mapped or removed.
    op.execute(
        "ALTER TABLE public.users ADD CONSTRAINT users_id_auth_users_fkey "
        "FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE NOT VALID"
    )

    for name, target in FOREIGN_KEY_INDEXES.items():
        op.execute(f"CREATE INDEX {name} ON public.{target}")

    for table in APPLICATION_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM anon, authenticated")


def downgrade() -> None:
    op.execute("ALTER TABLE public.users DROP CONSTRAINT users_id_auth_users_fkey")
    op.execute("ALTER TABLE public.users ALTER COLUMN id SET DEFAULT uuid_generate_v4()")
    op.execute("ALTER TABLE public.users ADD COLUMN clerk_user_id text")
    op.execute("UPDATE public.users SET clerk_user_id = 'legacy_' || id::text")
    op.execute("ALTER TABLE public.users ALTER COLUMN clerk_user_id SET NOT NULL")
    op.execute(
        "ALTER TABLE public.users ADD CONSTRAINT users_clerk_user_id_key UNIQUE (clerk_user_id)"
    )

    for name in FOREIGN_KEY_INDEXES:
        op.execute(f"DROP INDEX public.{name}")

    for table in APPLICATION_TABLES:
        if table != "user_llm_settings":
            op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
