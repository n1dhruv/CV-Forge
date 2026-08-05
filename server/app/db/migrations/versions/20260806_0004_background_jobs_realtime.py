"""Expose owned background job updates through Supabase Realtime."""

from alembic import op

revision = "20260806_0004"
down_revision = "20260805_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.background_jobs ENABLE ROW LEVEL SECURITY")
    op.execute(
        'CREATE POLICY "users can read their own jobs" '
        "ON public.background_jobs FOR SELECT TO authenticated "
        "USING ((SELECT auth.uid()) = user_id)"
    )
    op.execute("GRANT SELECT ON TABLE public.background_jobs TO authenticated")
    op.execute(
        """
        DO $migration$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_publication
                WHERE pubname = 'supabase_realtime'
            ) THEN
                RAISE EXCEPTION 'supabase_realtime publication is missing';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime'
                  AND schemaname = 'public'
                  AND tablename = 'background_jobs'
            ) THEN
                ALTER PUBLICATION supabase_realtime ADD TABLE public.background_jobs;
            END IF;
        END
        $migration$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $migration$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_publication_tables
                WHERE pubname = 'supabase_realtime'
                  AND schemaname = 'public'
                  AND tablename = 'background_jobs'
            ) THEN
                ALTER PUBLICATION supabase_realtime DROP TABLE public.background_jobs;
            END IF;
        END
        $migration$;
        """
    )
    op.execute("REVOKE SELECT ON TABLE public.background_jobs FROM authenticated")
    op.execute('DROP POLICY IF EXISTS "users can read their own jobs" ' "ON public.background_jobs")
