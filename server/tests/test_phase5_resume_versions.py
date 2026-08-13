from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import httpx
from fastapi import HTTPException

from app.api import resume_versions as resume_versions_api
from app.models.resume import ResumeVersion
from app.schemas.resume_version import ResumeMetadataUpdate
from app.services import resume_versions


def session_mock() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def test_resume_metadata_is_trimmed_and_nonempty() -> None:
    payload = ResumeMetadataUpdate(name="  Backend Resume  ", version_label="  Final  ")
    assert payload.name == "Backend Resume"
    assert payload.version_label == "Final"

    with pytest.raises(ValueError):
        ResumeMetadataUpdate(name="   ")


async def test_queue_assembly_moves_finalized_version_to_assembling(monkeypatch) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status="finalized")
    session = session_mock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    queued = await resume_versions.queue_assembly(session, version.user_id, version.id)

    assert queued and queued[0] is version
    assert version.status == "assembling"
    assert queued[1].job_type == "resume_assemble"
    session.commit.assert_awaited_once()


async def test_queue_assembly_rejects_non_finalized_version(monkeypatch) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status="draft")
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    with pytest.raises(resume_versions.InvalidResumeVersionStateError):
        await resume_versions.queue_assembly(session_mock(), version.user_id, version.id)


async def test_queue_assembly_recovers_existing_active_job(monkeypatch) -> None:
    owner = uuid4()
    version = ResumeVersion(id=uuid4(), user_id=owner, status="assembling")
    job = MagicMock(job_type="resume_assemble", status="queued")
    session = session_mock()
    session.scalar = AsyncMock(return_value=job)
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    queued = await resume_versions.queue_assembly(session, owner, version.id)

    assert queued == (version, job, False)
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("status", ["assembled", "compiled", "compile_failed"])
async def test_queue_compile_accepts_stable_source_states(monkeypatch, status) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status=status, tex_source="source")
    session = session_mock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    queued = await resume_versions.queue_compile(session, version.user_id, version.id)

    assert queued and queued[0].status == "compiling"
    assert queued[1].job_type == "resume_compile"
    assert queued[1].result["previous_status"] == status


async def test_source_update_invalidates_pdf_without_creating_a_row(monkeypatch) -> None:
    version = ResumeVersion(
        id=uuid4(), user_id=uuid4(), status="compiled", tex_source="old", pdf_storage_path="x.pdf"
    )
    session = session_mock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    result = await resume_versions.update_tex(session, version.user_id, version.id, "new")

    assert result is version
    assert (version.tex_source, version.status, version.pdf_storage_path) == (
        "new",
        "assembled",
        None,
    )
    session.add.assert_not_called()


async def test_snapshot_sets_parent_and_copies_stable_document(monkeypatch) -> None:
    version = ResumeVersion(
        id=uuid4(),
        user_id=uuid4(),
        jd_id=uuid4(),
        status="compiled",
        tex_source="source",
        pdf_storage_path="resume.pdf",
    )
    session = session_mock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    clone = await resume_versions.create_snapshot(session, version.user_id, version.id)

    assert clone and clone.parent_version_id == version.id
    assert clone.tex_source == "source" and clone.pdf_storage_path == "resume.pdf"
    session.add.assert_called_once_with(clone)


async def test_history_returns_ancestors_oldest_first(monkeypatch) -> None:
    owner = uuid4()
    root = ResumeVersion(
        id=uuid4(), user_id=owner, status="compiled", created_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    child = ResumeVersion(
        id=uuid4(),
        user_id=owner,
        status="assembled",
        parent_version_id=root.id,
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    session = AsyncMock()
    session.scalar.side_effect = [child, root]

    result = await resume_versions.history(session, owner, child.id)

    assert result == [root, child]


async def test_list_families_groups_descendants_under_root() -> None:
    owner = uuid4()
    root = ResumeVersion(id=uuid4(), user_id=owner, status="compiled", name="Backend", version_label="Initial", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    child = ResumeVersion(id=uuid4(), user_id=owner, status="compiled", name="Backend", version_label="Final", parent_version_id=root.id, created_at=datetime(2026, 1, 2, tzinfo=UTC))
    session = MagicMock()
    scalar_result = MagicMock()
    scalar_result.all.return_value = [root, child]
    session.scalars = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    result = await resume_versions.list_families(session, owner)

    assert result == [(root, [child, root])]


async def test_update_metadata_propagates_family_name_only() -> None:
    owner = uuid4()
    root = ResumeVersion(id=uuid4(), user_id=owner, status="compiled", name="Old", version_label="Initial")
    child = ResumeVersion(id=uuid4(), user_id=owner, status="compiled", name="Old", version_label="Draft", parent_version_id=root.id)
    session = MagicMock()
    scalar_result = MagicMock()
    scalar_result.all.return_value = [root, child]
    session.scalars = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    result = await resume_versions.update_metadata(session, owner, child.id, "New", "Final")

    assert result is child
    assert root.name == child.name == "New"
    assert root.version_label == "Initial" and child.version_label == "Final"
    session.commit.assert_awaited_once()


async def test_version_detail_normalizes_signed_url_failure(monkeypatch) -> None:
    version = ResumeVersion(
        id=uuid4(),
        user_id=uuid4(),
        status="compiled",
        tex_source="source",
        pdf_storage_path="resume.pdf",
        created_at=datetime.now(UTC),
        name="Resume",
        version_label="Initial",
    )
    session = session_mock()
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))
    monkeypatch.setattr(
        resume_versions_api.StorageService,
        "signed_download_url",
        AsyncMock(side_effect=httpx.ConnectError("storage unavailable")),
    )

    with pytest.raises(HTTPException) as error:
        await resume_versions_api.read_resume_version(
            version.id, session, type("User", (), {"id": version.user_id})(), MagicMock()
        )

    assert error.value.status_code == 502
