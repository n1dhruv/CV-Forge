from io import BytesIO
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from docx import Document
from sqlalchemy.dialects import postgresql

from app.models.resume import ResumeImport
from app.schemas.resume_import import ResumeImportCommit
from app.services import llm_client, resume_imports
from app.workers import resume_imports as worker


class Result:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


def pdf_with_text(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(content)


def test_pdf_fixture_extracts_resume_text() -> None:
    assert "Built Python APIs" in worker.extract_pdf_text(pdf_with_text("Built Python APIs"))


def test_docx_fixture_extracts_resume_text() -> None:
    document = Document()
    document.add_paragraph("Built Python APIs")
    content = BytesIO()
    document.save(content)

    assert worker.extract_docx_text(content.getvalue()) == "Built Python APIs"


async def test_sparse_resume_guardrail_rejects_invented_content(monkeypatch) -> None:
    source = "Project: Tiny API\nBuilt one Flask endpoint.\nSkill: Flask"
    invented = """{
      "items": [{"type": "project", "title": "Tiny API", "org": null,
      "start_date": null, "end_date": null,
      "bullets": ["Built and scaled a distributed Flask platform"]}],
      "skills": ["Flask", "Kubernetes"]
    }"""
    completion = AsyncMock(side_effect=[invented, invented])
    monkeypatch.setattr(llm_client, "get_completion", completion)

    assert await worker._validated_completion(uuid4(), source) is None
    assert completion.await_count == 2


async def test_valid_resume_output_matches_schema(monkeypatch) -> None:
    source = "Tiny API\nBuilt one Flask endpoint.\nFlask"
    output = """{
      "items": [{"type": "project", "title": "Tiny API", "org": null,
      "start_date": null, "end_date": null,
      "bullets": ["Built one Flask endpoint."]}],
      "skills": ["Flask"]
    }"""
    completion = AsyncMock(return_value=output)
    monkeypatch.setattr(llm_client, "get_completion", completion)

    parsed = await worker._validated_completion(uuid4(), source)

    assert parsed is not None
    assert parsed.items[0].title == "Tiny API"
    assert parsed.skills == ["Flask"]
    assert completion.await_args.kwargs["response_format"] == {"type": "json_object"}


def test_resume_prompt_contains_literal_only_guardrail() -> None:
    prompt = worker.prompt_for("Sparse resume")

    assert "literally present" in prompt
    assert "Never infer a skill, invent a metric, embellish a bullet" in prompt


class CommitSession:
    def __init__(self, resume_import):
        self.resume_import = resume_import
        self.items = []
        self.commit = AsyncMock()

    async def scalar(self, statement):
        del statement
        return self.resume_import

    def add_all(self, rows):
        self.items = rows

    async def scalars(self, statement):
        del statement
        return Result(self.items)


async def test_partial_commit_creates_only_submitted_items_and_bullets() -> None:
    user_id = uuid4()
    resume_import = ResumeImport(id=uuid4(), user_id=user_id, status="done")
    session = CommitSession(resume_import)
    payload = ResumeImportCommit.model_validate(
        {
            "items": [
                {
                    "type": "experience",
                    "title": "Kept role",
                    "org": "Acme",
                    "start_date": None,
                    "end_date": None,
                    "bullets": ["Kept bullet"],
                }
            ]
        }
    )

    items = await resume_imports.commit_import(session, user_id, resume_import.id, payload)

    assert items is not None and len(items) == 1
    assert items[0].source == "resume_import"
    assert [bullet.text for bullet in items[0].bullet_points] == ["Kept bullet"]
    assert resume_import.committed_at is not None


async def test_commit_creates_selected_skills_as_skill_bank_items() -> None:
    user_id = uuid4()
    resume_import = ResumeImport(id=uuid4(), user_id=user_id, status="done")
    session = CommitSession(resume_import)
    payload = ResumeImportCommit.model_validate({"skills": ["Python", "FastAPI"]})

    items = await resume_imports.commit_import(session, user_id, resume_import.id, payload)

    assert items is not None
    assert [(item.type, item.title) for item in items] == [
        ("skill", "Python"),
        ("skill", "FastAPI"),
    ]
    assert all(item.source == "resume_import" for item in items)


async def test_double_commit_is_rejected() -> None:
    user_id = uuid4()
    resume_import = ResumeImport(id=uuid4(), user_id=user_id, status="done")
    session = CommitSession(resume_import)
    payload = ResumeImportCommit.model_validate(
        {
            "items": [
                {
                    "type": "project",
                    "title": "Kept project",
                    "org": None,
                    "start_date": None,
                    "end_date": None,
                    "bullets": [],
                }
            ]
        }
    )
    await resume_imports.commit_import(session, user_id, resume_import.id, payload)

    with pytest.raises(resume_imports.ResumeImportAlreadyCommittedError):
        await resume_imports.commit_import(session, user_id, resume_import.id, payload)


async def test_submission_stages_only_import_and_job() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    await resume_imports.create_submission(session, uuid4(), "user/resume.pdf")

    rows = session.add_all.call_args.args[0]
    assert {type(row).__name__ for row in rows} == {"ResumeImport", "BackgroundJob"}


async def test_resume_import_lookup_is_owner_scoped() -> None:
    session = AsyncMock()
    session.scalar.return_value = None

    await resume_imports.get_owned(session, uuid4(), uuid4())

    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "resume_imports.user_id" in sql


def test_literal_text_rejoins_pdf_line_wrap_hyphenation() -> None:
    source = worker._literal_text("role-\nbased authoriza-\ntion")
    claim = worker._literal_text("role-based authorization")

    assert source == claim
