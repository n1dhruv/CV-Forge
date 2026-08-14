import asyncio
from datetime import date
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import AsyncMock

import pytest

from app.services import latex_compiler
from app.services.latex import LatexItem, LatexProfile, escape_latex, render_resume
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
    assert r"\n" not in first


def test_render_resume_groups_skill_categories_and_omits_empty_itemize() -> None:
    source = render_resume(
        [
            LatexItem(
                type="skill",
                title="Python",
                org=None,
                start_date=None,
                end_date=None,
                bullets=[],
                category="Languages",
            ),
            LatexItem(
                type="education",
                title="B.Tech Computer Science",
                org="Example University",
                start_date=date(2020, 1, 1),
                end_date=date(2024, 1, 1),
                bullets=[],
            ),
        ]
    )

    assert r"\textbf{Languages:} Python" in source
    assert "B.Tech Computer Science" in source
    assert r"\begin{itemize}" not in source


def test_render_resume_keeps_url_semantics_with_tex_safe_targets() -> None:
    url = "https://example.test/a_b%20c#fragment{value}"

    source = render_resume([], LatexProfile("Ada", None, None, None, url, None, None, None))

    assert r"\href{https://example.test/a\_b\%20c\#fragment\%7Bvalue\%7D}" in source


def test_parse_diagnostics_extracts_line_and_hides_raw_log() -> None:
    diagnostic = parse_diagnostics("error: Missing } inserted\n  --> resume.tex:42:8")

    assert diagnostic.kind == "syntax"
    assert diagnostic.line == 42
    assert diagnostic.message == "Missing } inserted"


def test_parse_diagnostics_skips_warnings_before_error() -> None:
    diagnostic = parse_diagnostics(
        "warning: cached font unavailable\nerror: Font metric missing\nresume.tex:10: stopped"
    )

    assert diagnostic.message == "Font metric missing"


def test_compile_latex_returns_pdf_bytes(monkeypatch, tmp_path) -> None:
    def run(command, **kwargs):
        assert kwargs["shell"] is False
        assert "--only-cached" not in command
        assert "--untrusted" in command
        assert kwargs["env"]["TECTONIC_UNTRUSTED_MODE"] == "1"
        assert kwargs["env"]["SOURCE_DATE_EPOCH"] == "0"
        (tmp_path / "resume.pdf").write_bytes(b"%PDF-test")
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr("app.services.latex_compiler.subprocess.run", run)
    monkeypatch.setattr(
        "app.services.latex_compiler.PdfReader", lambda _: type("Pdf", (), {"pages": [1]})()
    )

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


def test_compile_latex_keeps_error_after_many_warnings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(
        "app.services.latex_compiler.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args[0], 1, "", "warning: font lookup\n" * 2_000 + "error: Font metric missing\nresume.tex:10: stopped",
        ),
    )

    with pytest.raises(CompilationError) as error:
        compile_latex("source", "tectonic", 30)

    assert error.value.diagnostic.message == "Font metric missing"
    assert error.value.diagnostic.line == 10


def test_compile_latex_rejects_a_pdf_that_is_not_one_page(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(
        "app.services.latex_compiler.subprocess.run",
        lambda command, **kwargs: (
            (tmp_path / "resume.pdf").write_bytes(b"%PDF-test"),
            CompletedProcess(command, 0, "", ""),
        )[1],
    )
    monkeypatch.setattr(
        "app.services.latex_compiler.PdfReader", lambda _: type("Pdf", (), {"pages": [1, 2]})()
    )

    with pytest.raises(CompilationError) as error:
        compile_latex("source", "tectonic", 30)

    assert error.value.diagnostic.kind == "layout"
    assert error.value.diagnostic.message == "Resume must fit exactly one page"


def test_compile_latex_normalizes_an_unreadable_pdf(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(
        "app.services.latex_compiler.subprocess.run",
        lambda command, **kwargs: (
            (tmp_path / "resume.pdf").write_bytes(b"not-a-pdf"),
            CompletedProcess(command, 0, "", ""),
        )[1],
    )
    monkeypatch.setattr(
        "app.services.latex_compiler.PdfReader",
        lambda _: (_ for _ in ()).throw(ValueError("parser detail")),
    )

    with pytest.raises(CompilationError) as error:
        compile_latex("source", "tectonic", 30)

    assert error.value.diagnostic.kind == "internal"
    assert error.value.diagnostic.message == "The compiled PDF could not be validated"


async def test_async_compile_times_out_and_kills_the_process(monkeypatch, tmp_path) -> None:
    process_finished = asyncio.Event()

    class Process:
        returncode = None
        killed = False
        calls = 0

        async def communicate(self):
            self.calls += 1
            if self.calls == 1:
                await process_finished.wait()
            return b"", b""

        def kill(self):
            self.killed = True
            process_finished.set()

    process = Process()
    monkeypatch.setattr(latex_compiler, "TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=process))

    with pytest.raises(CompilationError) as error:
        await latex_compiler.compile_latex_async("source", "tectonic", 0.001)

    assert error.value.diagnostic.kind == "timeout"
    assert process.killed is True


async def test_async_compile_returns_one_page_pdf(monkeypatch, tmp_path) -> None:
    class Process:
        returncode = 0

        async def communicate(self):
            (tmp_path / "resume.pdf").write_bytes(b"%PDF-test")
            return b"", b""

    monkeypatch.setattr(latex_compiler, "TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=Process()))
    monkeypatch.setattr(
        latex_compiler, "PdfReader", lambda _: type("Pdf", (), {"pages": [object()]})()
    )

    pdf = await latex_compiler.compile_latex_async("source", "tectonic", 30)

    assert pdf == b"%PDF-test"


async def test_async_compile_uses_native_subprocess_and_normalizes_unreadable_pdf(
    monkeypatch, tmp_path
) -> None:
    compiler = getattr(latex_compiler, "compile_latex_async", None)
    assert compiler is not None

    class Process:
        returncode = 0

        async def communicate(self):
            (tmp_path / "resume.pdf").write_bytes(b"not-a-pdf")
            await asyncio.sleep(0)
            return b"", b""

        def kill(self):
            raise AssertionError("successful compiler must not be killed")

    async def create_subprocess(*command, **kwargs):
        assert "--untrusted" in command
        assert kwargs["env"]["TECTONIC_UNTRUSTED_MODE"] == "1"
        return Process()

    monkeypatch.setattr(latex_compiler, "TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    monkeypatch.setattr(
        latex_compiler,
        "PdfReader",
        lambda _: (_ for _ in ()).throw(ValueError("parser detail")),
    )

    with pytest.raises(CompilationError) as error:
        await compiler("source", "tectonic", 30)

    assert error.value.diagnostic.kind == "internal"
    assert error.value.diagnostic.message == "The compiled PDF could not be validated"


def test_assembly_compile_can_measure_a_multi_page_pdf(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("app.services.latex_compiler.TemporaryDirectory", lambda: _Temp(tmp_path))
    monkeypatch.setattr(
        "app.services.latex_compiler.subprocess.run",
        lambda command, **kwargs: (
            (tmp_path / "resume.pdf").write_bytes(b"%PDF-test"),
            CompletedProcess(command, 0, "", ""),
        )[1],
    )
    monkeypatch.setattr(
        "app.services.latex_compiler.PdfReader", lambda _: type("Pdf", (), {"pages": [1, 2]})()
    )

    assert compile_latex("source", "tectonic", 30, enforce_one_page=False) == b"%PDF-test"


class _Temp:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return str(self.path)

    def __exit__(self, *args):
        return None
