import importlib.util
from pathlib import Path


def test_realtime_access_is_authenticated_and_owner_scoped(monkeypatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "app/db/migrations/versions/20260806_0004_background_jobs_realtime.py"
    )
    spec = importlib.util.spec_from_file_location("background_jobs_realtime", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()
    sql = "\n".join(statements).lower()

    assert "enable row level security" in sql
    assert "for select to authenticated" in sql
    assert "using ((select auth.uid()) = user_id)" in sql
    assert "grant select on table public.background_jobs to authenticated" in sql
    assert "alter publication supabase_realtime add table public.background_jobs" in sql
    assert " to anon" not in sql
    assert "grant insert" not in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql
