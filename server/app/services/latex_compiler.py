import re
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal


@dataclass(frozen=True)
class CompileDiagnostic:
    kind: Literal["syntax", "timeout", "internal"]
    message: str
    line: int | None = None


class CompilationError(Exception):
    def __init__(self, diagnostic: CompileDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def parse_diagnostics(output: str) -> CompileDiagnostic:
    line_match = re.search(r"resume\.tex:(\d+)(?::\d+)?", output)
    message_match = re.search(r"(?:^|\n)error:\s*([^\n]+)", output, re.IGNORECASE)
    if message_match is None:
        message_match = re.search(r"(?:^|\n)(?!warning:)([^\n]+)", output, re.IGNORECASE)
    message = message_match.group(1).strip() if message_match else "LaTeX compilation failed"
    if message.lower().startswith("error:"):
        message = message[6:].strip()
    return CompileDiagnostic(
        "syntax", message[:500], int(line_match.group(1)) if line_match else None
    )


def compile_latex(source: str, binary_path: str, timeout_seconds: int) -> bytes:
    with TemporaryDirectory() as directory:
        workdir = Path(directory)
        source_path = workdir / "resume.tex"
        source_path.write_text(source, encoding="utf-8")
        command = [
            binary_path,
            "--only-cached",
            "--untrusted",
            "--keep-logs",
            "--outdir",
            str(workdir),
            str(source_path),
        ]
        try:
            result = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
                env={
                    **os.environ,
                    "SOURCE_DATE_EPOCH": "0",
                    "TECTONIC_UNTRUSTED_MODE": "1",
                },
            )
        except subprocess.TimeoutExpired as exc:
            raise CompilationError(
                CompileDiagnostic("timeout", "LaTeX compilation timed out")
            ) from exc
        except OSError as exc:
            raise CompilationError(
                CompileDiagnostic("internal", "The LaTeX compiler is unavailable")
            ) from exc

        pdf_path = workdir / "resume.pdf"
        if result.returncode or not pdf_path.is_file() or not pdf_path.stat().st_size:
            output = (result.stderr + "\n" + result.stdout)[-20_000:]
            raise CompilationError(parse_diagnostics(output))
        return pdf_path.read_bytes()
