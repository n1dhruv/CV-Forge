from datetime import date
from subprocess import CompletedProcess, TimeoutExpired

import pytest

from app.services.latex import LatexItem, escape_latex, render_resume
from app.services.latex_compiler import CompilationError, compile_latex, parse_diagnostics


def test_escape_latex_handles_every_special_character_once() -> None:
    assert escape_latex(r"\{}$&#%_~^") == (
        r"\textbackslash{}\{\}\$\&\#\%\_\textasciitilde{}\textasciicircum{}"
    )


def test_render_resume_is_deterministic_and_omits_empty_sections() -> None:
    items = [
        LatexItem(
            type="experience",
            title="R&D Engineer",
            org="A&B",
            start_date=date(2024, 1, 1),
            end_date=None,
            bullets=["Cut latency by 20%"],
        )
    ]

    first = render_resume(items)

    assert first == render_resume(items)
    assert r"R\&D Engineer" in first
    assert r"A\&B" in first
    assert r"Cut latency by 20\%" in first
    assert "Experience" in first
    assert "Education" not in first


def test_parse_diagnostics_extracts_line_and_hides_raw_log() -> None:
    diagnostic = parse_diagnostics("error: Missing } inserted\n  --> resume.tex:42:8")

    assert diagnostic.kind == "syntax"
    assert diagnostic.line == 42
    assert diagnostic.message == "Missing } inserted"


def test_compile_latex_returns_pdf_bytes(monkeypatch, tmp_path) -> None:
    def run(command, **kwargs):
        assert kwargs["shell"] is False
        assert "--only-cached" in command
        assert "--untrusted" in command
        assert kwargs["env"]["TECTONIC_UNTRUSTED_MODE"] == "1"
        assert kwargs["env"]["SOURCE_DATE_EPOCH"] == "0"
        (tmp_path / "resume.pdf").write_bytes(b"%PDF-test")
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr("app.services.latex_compiler.subprocess.run", run)

    assert compile_latex("source", "tectonic", 30) == b"%PDF-test"


def test_compile_latex_normalizes_timeout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(
        "app.services.latex_compiler.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutExpired("tectonic", 30)),
    )

    with pytest.raises(CompilationError) as error:
        compile_latex("source", "tectonic", 30)

    assert error.value.diagnostic.kind == "timeout"
    assert error.value.diagnostic.line is None


class _Temp:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return str(self.path)

    def __exit__(self, *args):
        return None
