from uuid import uuid4

from app.models.jobs import BackgroundJob
from app.models.resume import ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import SkillBankItem
from app.workers.resume_assembly import latex_items_from_rows
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


def test_phase5_background_job_types() -> None:
    assert BackgroundJob(job_type="resume_assemble", status="queued").job_type == "resume_assemble"
    assert BackgroundJob(job_type="resume_compile", status="queued").job_type == "resume_compile"


def test_compile_failure_keeps_source_and_stores_structured_diagnostic() -> None:
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
    assert version.status == "compile_failed" and version.pdf_storage_path is None
    assert job.status == "failed"
    assert job.result["errors"] == [{"kind": "syntax", "message": "Missing } inserted", "line": 12}]
