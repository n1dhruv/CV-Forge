from uuid import uuid4
from unittest.mock import AsyncMock

from app.models.jobs import BackgroundJob
from app.models.resume import ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import SkillBankItem
from app.workers import resume_assembly
from app.workers.resume_assembly import latex_items_from_rows, render_one_page_resume
from app.workers.resume_compile import _record_failure
from app.services.latex_compiler import CompileDiagnostic


def test_assembly_uses_approved_and_reverted_text_and_groups_items() -> None:
    item = SkillBankItem(
        id=uuid4(), user_id=uuid4(), type="experience", title="Engineer", bullet_points=[]
    )
    approved = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=uuid4(),
        bullet_point_id=uuid4(),
        original_text="Original approved",
        rewritten_text="Approved rewrite",
        approved=True,
        resolved=True,
        flagged_terms=[],
        section_order=0,
    )
    reverted = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=approved.resume_version_id,
        bullet_point_id=uuid4(),
        original_text="Original kept",
        rewritten_text="Original kept",
        approved=False,
        resolved=True,
        flagged_terms=[],
        section_order=1,
    )

    result = latex_items_from_rows([(approved, item), (reverted, item)])

    assert len(result) == 1
    assert result[0].bullets == ["Approved rewrite", "Original kept"]


def test_assembly_rejects_unresolved_selection() -> None:
    item = SkillBankItem(id=uuid4(), user_id=uuid4(), type="project", title="Project")
    selection = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=uuid4(),
        bullet_point_id=uuid4(),
        original_text="Original",
        rewritten_text="Rewrite",
        approved=False,
        resolved=False,
        flagged_terms=[],
    )

    try:
        latex_items_from_rows([(selection, item)])
    except ValueError as error:
        assert str(error) == "Every bullet must be resolved before assembly"
    else:
        raise AssertionError("unresolved selection was accepted")


def test_assembly_adds_selected_skill_snapshot_and_mandatory_education() -> None:
    experience = SkillBankItem(
        id=uuid4(), user_id=uuid4(), type="experience", title="Engineer", bullet_points=[]
    )
    education = SkillBankItem(
        id=uuid4(), user_id=experience.user_id, type="education", title="B.Tech", bullet_points=[]
    )
    selection = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=uuid4(),
        bullet_point_id=uuid4(),
        original_text="Built APIs",
        rewritten_text="Built APIs",
        approved=False,
        resolved=True,
        flagged_terms=[],
        section_order=0,
    )

    result = latex_items_from_rows(
        [(selection, experience)],
        [{"item_id": str(uuid4()), "name": "Python", "category": "Languages", "selection_order": 1}],
        education,
    )

    assert [(item.type, item.title, item.category) for item in result] == [
        ("experience", "Engineer", None),
        ("skill", "Python", "Languages"),
        ("education", "B.Tech", None),
    ]


async def test_assembly_removes_lowest_priority_optional_content_until_one_page(monkeypatch) -> None:
    item = SkillBankItem(id=uuid4(), user_id=uuid4(), type="experience", title="Engineer")
    first = ResumeBulletSelection(
        id=uuid4(), resume_version_id=uuid4(), bullet_point_id=uuid4(), original_text="Keep me",
        rewritten_text="Keep me", approved=False, resolved=True, flagged_terms=[], section_order=0,
    )
    second = ResumeBulletSelection(
        id=uuid4(), resume_version_id=first.resume_version_id, bullet_point_id=uuid4(),
        original_text="Drop me", rewritten_text="Drop me", approved=False, resolved=True,
        flagged_terms=[], section_order=1,
    )
    pages = iter(([object(), object()], [object()]))
    monkeypatch.setattr(resume_assembly.asyncio, "to_thread", AsyncMock(return_value=b"pdf"))
    monkeypatch.setattr(
        resume_assembly, "PdfReader", lambda _: type("Pdf", (), {"pages": next(pages)})()
    )

    source = await render_one_page_resume(
        [(first, item), (second, item)], [], None, None, "tectonic", 30
    )

    assert "Keep me" in source
    assert "Drop me" not in source


def test_phase5_background_job_types() -> None:
    assert BackgroundJob(job_type="resume_assemble", status="queued").job_type == "resume_assemble"
    assert BackgroundJob(job_type="resume_compile", status="queued").job_type == "resume_compile"


def test_compile_failure_keeps_source_pdf_and_stores_structured_diagnostic() -> None:
    version = ResumeVersion(
        id=uuid4(),
        user_id=uuid4(),
        status="compiling",
        tex_source="broken source",
        pdf_storage_path="stale.pdf",
    )
    job = BackgroundJob(id=uuid4(), user_id=version.user_id, status="running")

    _record_failure(version, job, CompileDiagnostic("syntax", "Missing } inserted", 12))

    assert version.tex_source == "broken source"
    assert version.status == "compile_failed" and version.pdf_storage_path == "stale.pdf"
    assert job.status == "failed"
    assert job.result["errors"] == [{"kind": "syntax", "message": "Missing } inserted", "line": 12}]
