from app import cli


def test_app_command_starts_expected_uvicorn_application(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_run(application: str, *, reload: bool) -> None:
        calls.append((application, reload))

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

    cli.main()

    assert calls == [("app.main:app", True)]
