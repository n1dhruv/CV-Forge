import importlib


def test_links_migration_is_backward_compatible_and_reversible(monkeypatch) -> None:
    migration = importlib.import_module(
        "app.db.migrations.versions.20260815_0012_skill_bank_links"
    )
    added = []
    checks = []
    removed = []
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added.append((table, column.name, column.nullable, str(column.server_default.arg))),
    )
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: checks.append((name, table, condition)),
    )
    monkeypatch.setattr(migration.op, "drop_constraint", lambda name, table, type_: removed.append(("constraint", name, table, type_)))
    monkeypatch.setattr(migration.op, "drop_column", lambda table, name: removed.append(("column", table, name)))

    migration.upgrade()
    migration.downgrade()

    assert migration.down_revision == "20260814_0011"
    assert added == [("skill_bank_items", "links", False, "'[]'::jsonb")]
    assert checks and "jsonb_array_length(links) <= 2" in checks[0][2]
    assert removed[-1] == ("column", "skill_bank_items", "links")
