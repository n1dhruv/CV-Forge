from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql
from starlette.requests import Request

from app.api.jd import routes
from app.api.jobs import read_background_job
from app.core.config import get_settings
from app.models.jobs import BackgroundJob
from app.models.resume import JobDescription
from app.models.user import User
from app.services import jd, jobs, llm_client
from app.workers import jd as worker


class FakeSession:
    def __init__(self, *scalar_results: object) -> None:
        self.scalar = AsyncMock(side_effect=scalar_results)
        self.get = AsyncMock()
        self.add_all = MagicMock()
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


def parsed_output() -> str:
    return """{
        "required_skills": ["Python", "PostgreSQL"],
        "nice_to_have_skills": ["FastAPI"],
        "responsibilities": ["Build APIs"],
        "seniority": "senior",
        "ats_keywords": ["async", "REST"]
    }"""


async def test_successful_pasted_text_parse_persists_validated_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    description = JobDescription(
        id=jd_id, user_id=user_id, raw_text="Senior Python engineer", status="queued"
    )
    background_job = BackgroundJob(id=job_id, user_id=user_id, job_type="jd_parse", status="queued")
    final_session = FakeSession(description, background_job)
    monkeypatch.setattr(llm_client, "ensure_configured", AsyncMock())
    monkeypatch.setattr(llm_client, "get_completion", AsyncMock(return_value=parsed_output()))
    monkeypatch.setattr(worker, "_load_rows", AsyncMock(return_value=(description, background_job)))
    set_status = AsyncMock()
    monkeypatch.setattr(worker, "_set_status", set_status)
    monkeypatch.setattr(worker, "async_session_factory", lambda: final_session)

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert description.status == "done"
    assert description.parsed_json == {
        "required_skills": ["Python", "PostgreSQL"],
        "nice_to_have_skills": ["FastAPI"],
        "responsibilities": ["Build APIs"],
        "seniority": "senior",
        "ats_keywords": ["async", "REST"],
    }
    requirements = final_session.add_all.call_args.args[0]
    assert {(item.skill, item.importance) for item in requirements} == {
        ("Python", "required"),
        ("PostgreSQL", "required"),
        ("FastAPI", "nice_to_have"),
    }
    assert background_job.status == "done"
    assert background_job.result == {"required_skills": 2, "nice_to_have_skills": 1}
    final_session.commit.assert_awaited_once()


async def test_malformed_output_retries_once_then_fails_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    description = JobDescription(id=jd_id, user_id=user_id, raw_text="A valid JD", status="queued")
    background_job = BackgroundJob(id=job_id, user_id=user_id, job_type="jd_parse", status="queued")
    completion = AsyncMock(side_effect=["garbage", "still garbage"])
    monkeypatch.setattr(llm_client, "ensure_configured", AsyncMock())
    monkeypatch.setattr(llm_client, "get_completion", completion)
    monkeypatch.setattr(worker, "_load_rows", AsyncMock(return_value=(description, background_job)))
    set_status = AsyncMock()
    monkeypatch.setattr(worker, "_set_status", set_status)

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert completion.await_count == 2
    assert description.parsed_json is None
    assert set_status.await_args.kwargs["error"] == worker.INVALID_OUTPUT_ERROR


async def test_no_llm_settings_fails_before_loading_jd_or_calling_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    monkeypatch.setattr(
        llm_client,
        "ensure_configured",
        AsyncMock(side_effect=llm_client.LLMNotConfiguredError()),
    )
    load_rows = AsyncMock()
    completion = AsyncMock()
    set_status = AsyncMock()
    monkeypatch.setattr(worker, "_load_rows", load_rows)
    monkeypatch.setattr(worker, "_set_status", set_status)
    monkeypatch.setattr(llm_client, "get_completion", completion)

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    load_rows.assert_not_awaited()
    completion.assert_not_awaited()
    assert set_status.await_args.kwargs["error"] == worker.NO_LLM_ERROR


async def test_settings_deleted_during_parse_marks_job_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    description = JobDescription(id=jd_id, user_id=user_id, raw_text="A valid JD", status="queued")
    background_job = BackgroundJob(id=job_id, user_id=user_id, job_type="jd_parse", status="queued")
    monkeypatch.setattr(llm_client, "ensure_configured", AsyncMock())
    monkeypatch.setattr(
        llm_client,
        "get_completion",
        AsyncMock(side_effect=llm_client.LLMNotConfiguredError()),
    )
    monkeypatch.setattr(worker, "_load_rows", AsyncMock(return_value=(description, background_job)))
    set_status = AsyncMock()
    monkeypatch.setattr(worker, "_set_status", set_status)

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert set_status.await_args.kwargs["error"] == worker.NO_LLM_ERROR


async def test_blank_pdf_fails_with_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    description = JobDescription(
        id=jd_id,
        user_id=user_id,
        raw_text=None,
        source_file_url=f"{user_id}/blank.pdf",
        status="queued",
    )
    background_job = BackgroundJob(id=job_id, user_id=user_id, job_type="jd_parse", status="queued")
    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"%PDF-empty")
    monkeypatch.setattr(llm_client, "ensure_configured", AsyncMock())
    monkeypatch.setattr(worker, "_load_rows", AsyncMock(return_value=(description, background_job)))
    monkeypatch.setattr(worker, "StorageService", MagicMock(return_value=storage))
    monkeypatch.setattr(worker.asyncio, "to_thread", AsyncMock(return_value=""))
    set_status = AsyncMock()
    monkeypatch.setattr(worker, "_set_status", set_status)

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert set_status.await_args.kwargs["error"] == worker.PDF_TEXT_ERROR


async def test_uploaded_pdf_extracts_text_before_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    description = JobDescription(
        id=jd_id,
        user_id=user_id,
        raw_text=None,
        source_file_url=f"{user_id}/jd.pdf",
        status="queued",
    )
    background_job = BackgroundJob(id=job_id, user_id=user_id, job_type="jd_parse", status="queued")
    extracted_text = "Senior Python engineer building reliable APIs and PostgreSQL systems."
    extraction_session = FakeSession()
    extraction_session.get.return_value = description
    final_session = FakeSession(description, background_job)
    sessions = iter([extraction_session, final_session])
    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"%PDF-fixture")
    monkeypatch.setattr(llm_client, "ensure_configured", AsyncMock())
    completion = AsyncMock(return_value=parsed_output())
    monkeypatch.setattr(llm_client, "get_completion", completion)
    monkeypatch.setattr(worker, "_load_rows", AsyncMock(return_value=(description, background_job)))
    monkeypatch.setattr(worker, "_set_status", AsyncMock())
    monkeypatch.setattr(worker, "StorageService", MagicMock(return_value=storage))
    monkeypatch.setattr(worker.asyncio, "to_thread", AsyncMock(return_value=extracted_text))
    monkeypatch.setattr(worker, "async_session_factory", lambda: next(sessions))

    await worker.parse_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert description.raw_text == extracted_text
    assert completion.await_args.args[1][0]["content"].endswith(extracted_text)
    assert description.status == "done"


async def test_uploaded_pdf_is_stored_without_synchronous_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body_request = httpx.Request(
        "POST",
        "http://test/api/jd/parse",
        files={"file": ("jd.pdf", b"%PDF-test", "application/pdf")},
    )
    body = body_request.read()
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/jd/parse",
            "headers": [(key.lower(), value) for key, value in body_request.headers.raw],
        },
        receive,
    )
    storage = MagicMock()
    storage.upload = AsyncMock(return_value="path")
    monkeypatch.setattr(routes, "StorageService", MagicMock(return_value=storage))

    raw_text, path = await routes._parse_submission(request, uuid4(), get_settings())

    assert raw_text is None
    assert path is not None and path.endswith(".pdf")
    storage.upload.assert_awaited_once()


async def test_submit_returns_ids_after_enqueue_without_running_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(id=uuid4(), clerk_user_id="user_a", email="a@example.com")
    description = JobDescription(
        id=uuid4(), user_id=user.id, raw_text="Python role", status="queued"
    )
    background_job = BackgroundJob(
        id=uuid4(), user_id=user.id, job_type="jd_parse", status="queued"
    )
    queue = MagicMock()
    queue.enqueue_job = AsyncMock(return_value=object())
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(arq=queue)))
    monkeypatch.setattr(routes, "_parse_submission", AsyncMock(return_value=("Python role", None)))
    monkeypatch.setattr(
        jd, "create_submission", AsyncMock(return_value=(description, background_job))
    )

    response = await routes.submit_jd(request, AsyncMock(), user, get_settings())

    assert response.job_description_id == description.id
    assert response.background_job_id == background_job.id
    queue.enqueue_job.assert_awaited_once()


async def test_jd_and_job_queries_enforce_ownership() -> None:
    session = AsyncMock()
    session.scalar.return_value = None
    user_id = uuid4()

    await jd.get_owned_jd(session, user_id, uuid4())
    jd_sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))
    await jobs.get_owned_job(session, user_id, uuid4())
    job_sql = str(session.scalar.await_args.args[0].compile(dialect=postgresql.dialect()))

    assert "job_descriptions.user_id" in jd_sql
    assert "background_jobs.user_id" in job_sql


async def test_foreign_jd_and_job_return_404(monkeypatch: pytest.MonkeyPatch) -> None:
    user_b = User(id=uuid4(), clerk_user_id="user_b", email="b@example.com")
    monkeypatch.setattr(jd, "get_owned_jd", AsyncMock(return_value=None))
    monkeypatch.setattr(jobs, "get_owned_job", AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as jd_error:
        await routes.read_jd(uuid4(), AsyncMock(), user_b)
    with pytest.raises(HTTPException) as job_error:
        await read_background_job(uuid4(), AsyncMock(), user_b)

    assert jd_error.value.status_code == 404
    assert job_error.value.status_code == 404


async def test_generic_job_endpoint_reflects_all_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=uuid4(), clerk_user_id="user_a", email="a@example.com")
    job_id = uuid4()
    for status in ("queued", "running", "done", "failed"):
        job = BackgroundJob(
            id=job_id,
            user_id=user.id,
            job_type="jd_parse",
            status=status,
            result={"ok": True} if status == "done" else None,
            error="failed" if status == "failed" else None,
        )
        monkeypatch.setattr(jobs, "get_owned_job", AsyncMock(return_value=job))

        response = await read_background_job(job_id, AsyncMock(), user)

        assert response.status == status


def test_llm_input_is_capped_with_note() -> None:
    capped = worker.capped_jd_text("x" * 20_000)

    assert len(capped) == worker.MAX_LLM_CHARACTERS
    assert capped.endswith("[JD truncated to 15,000 characters.]")
