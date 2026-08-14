import importlib


def test_resume_profile_migration_adds_only_profile_skill_and_selection_columns(monkeypatch) -> None:
    migration = importlib.import_module(
        "app.db.migrations.versions.20260814_0011_resume_profile"
    )
    added: list[tuple[str, str, bool, str | None]] = []
    removed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append(
            (
                table,
                column.name,
                column.nullable,
                str(column.server_default.arg) if column.server_default else None,
            )
        ),
    )
    monkeypatch.setattr(migration.op, "drop_column", lambda table, name: removed.append((table, name)))

    migration.upgrade()
    migration.downgrade()

    assert migration.down_revision == "20260813_0010"
    assert added == [
        ("users", "full_name", True, None),
        ("users", "contact_email", True, None),
        ("users", "phone", True, None),
        ("users", "location", True, None),
        ("users", "linkedin_url", True, None),
        ("users", "github_url", True, None),
        ("users", "leetcode_url", True, None),
        ("users", "portfolio_url", True, None),
        ("skill_bank_items", "skill_category", True, None),
        ("resume_versions", "selected_skills", False, "'[]'::jsonb"),
    ]
    assert removed == [(table, name) for table, name, _, _ in reversed(added)]
