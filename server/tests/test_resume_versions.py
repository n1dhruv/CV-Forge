from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.api import resume_versions as resume_versions_api
from app.models.jobs import BackgroundJob
from app.models.resume import ResumeBulletSelection, ResumeVersion
from app.models.skill_bank import BulletPoint
from app.models.user import User
from app.schemas.resume_version import ResumeBulletSelectionUpdate
from app.services import resume_versions


class ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


async def test_version_lookup_is_owner_scoped() -> None:
    session = AsyncMock()
    session.scalar.return_value = None

    await resume_versions.get_owned(session, uuid4(), uuid4())

    sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "resume_versions.user_id" in sql


async def test_selection_lookup_is_owner_scoped() -> None:
    result = MagicMock()
    result.one_or_none.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    await resume_versions.get_selection_owned(session, uuid4(), uuid4())

    sql = str(session.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "resume_versions.user_id" in sql
    assert "resume_bullet_selections.id" in sql


async def test_finalize_reports_unresolved_bullets_without_mutating_status(monkeypatch) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status="reviewing")
    unresolved = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=version.id,
        bullet_point_id=uuid4(),
        original_text="Original",
        rewritten_text="Rewrite",
        approved=False,
        resolved=False,
        flagged_terms=[],
        low_effort_rewrite=False,
        section_order=0,
    )
    session = AsyncMock()
    session.scalars.return_value = ScalarResult([unresolved])
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    result = await resume_versions.finalize(session, version.user_id, version.id)

    assert result == (version, [unresolved.id])
    assert version.status == "reviewing"
    session.commit.assert_not_awaited()


async def test_finalize_requires_an_explicit_resolution(monkeypatch) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status="reviewing")
    approved = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=version.id,
        bullet_point_id=uuid4(),
        original_text="Original",
        rewritten_text="Rewrite",
        approved=True,
        resolved=True,
        flagged_terms=[],
        low_effort_rewrite=False,
    )
    reverted = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=version.id,
        bullet_point_id=uuid4(),
        original_text="Kept original",
        rewritten_text="Kept original",
        approved=False,
        resolved=True,
        flagged_terms=[],
        low_effort_rewrite=False,
    )
    session = AsyncMock()
    session.scalars.return_value = ScalarResult([approved, reverted])
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    result = await resume_versions.finalize(session, version.user_id, version.id)

    assert result == (version, [])
    assert version.status == "finalized"
    session.commit.assert_awaited_once()


async def test_non_draft_version_cannot_queue_rewrite(monkeypatch) -> None:
    version = ResumeVersion(id=uuid4(), user_id=uuid4(), status="reviewing")
    monkeypatch.setattr(resume_versions, "get_owned", AsyncMock(return_value=version))

    with pytest.raises(resume_versions.InvalidResumeVersionStateError):
        await resume_versions.queue_rewrite(AsyncMock(), version.user_id, version.id, [uuid4()])


def review_rows() -> tuple[User, ResumeVersion, ResumeBulletSelection, BulletPoint]:
    user = User(id=uuid4(), email="owner@example.test")
    version = ResumeVersion(id=uuid4(), user_id=user.id, status="reviewing")
    source = BulletPoint(id=uuid4(), item_id=uuid4(), text="Improved latency by 20%")
    selection = ResumeBulletSelection(
        id=uuid4(),
        resume_version_id=version.id,
        bullet_point_id=source.id,
        original_text="Source truth",
        rewritten_text="Tailored wording",
        approved=False,
        resolved=False,
        flagged_terms=[],
        low_effort_rewrite=False,
        section_order=0,
    )
    return user, version, selection, source


async def test_approving_selection_persists_without_changing_source(monkeypatch) -> None:
    user, version, selection, source = review_rows()
    session = AsyncMock()
    monkeypatch.setattr(
        resume_versions,
        "get_selection_owned",
        AsyncMock(return_value=(selection, version)),
    )

    result = await resume_versions_api.update_resume_bullet(
        selection.id,
        ResumeBulletSelectionUpdate(approved=True),
        session,
        user,
    )

    assert result.approved is True and result.resolved is True
    assert source.text == "Improved latency by 20%"
    session.commit.assert_awaited_once()


async def test_editing_selection_resets_approval(monkeypatch) -> None:
    user, version, selection, _ = review_rows()
    selection.original_text = "Improved latency by 20%"
    selection.rewritten_text = "Reduced latency by 20%"
    selection.approved = True
    selection.resolved = True
    selection.low_effort_rewrite = True
    session = AsyncMock()
    monkeypatch.setattr(
        resume_versions,
        "get_selection_owned",
        AsyncMock(return_value=(selection, version)),
    )

    result = await resume_versions_api.update_resume_bullet(
        selection.id,
        ResumeBulletSelectionUpdate(rewritten_text="Lowered latency by 20%"),
        session,
        user,
    )

    assert result.rewritten_text == "Lowered latency by 20%"
    assert result.approved is False and result.resolved is False
    assert result.low_effort_rewrite is False


async def test_editing_selection_cannot_change_a_metric(monkeypatch) -> None:
    user, version, selection, _ = review_rows()
    selection.original_text = "Improved latency by 20%"
    session = AsyncMock()
    monkeypatch.setattr(
        resume_versions,
        "get_selection_owned",
        AsyncMock(return_value=(selection, version)),
    )

    with pytest.raises(HTTPException) as error:
        await resume_versions_api.update_resume_bullet(
            selection.id,
            ResumeBulletSelectionUpdate(rewritten_text="Improved latency by 30%"),
            session,
            user,
        )

    assert error.value.status_code == 422
    session.commit.assert_not_awaited()


async def test_reverting_selection_is_an_explicit_resolution(monkeypatch) -> None:
    user, version, selection, _ = review_rows()
    selection.low_effort_rewrite = True
    session = AsyncMock()
    monkeypatch.setattr(
        resume_versions,
        "get_selection_owned",
        AsyncMock(return_value=(selection, version)),
    )

    result = await resume_versions_api.update_resume_bullet(
        selection.id,
        ResumeBulletSelectionUpdate(revert=True),
        session,
        user,
    )

    assert result.rewritten_text == "Source truth"
    assert result.approved is False and result.resolved is True
    assert result.low_effort_rewrite is False


def test_rewrite_background_job_type() -> None:
    assert BackgroundJob(job_type="rewrite", status="queued").job_type == "rewrite"
