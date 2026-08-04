from json import JSONDecodeError
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.jd import (
    JDDetail,
    JDListItem,
    JDParsed,
    JDParseQueued,
    JDRequirementRead,
    JDTextSubmission,
)
from app.services import jd
from app.services.storage import StorageService

router = APIRouter(prefix="/api/jd", tags=["job-descriptions"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
MAX_PDF_BYTES = 10 * 1024 * 1024


async def _parse_submission(
    request: Request, user_id: UUID, settings: Settings
) -> tuple[str | None, str | None]:
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        try:
            payload = JDTextSubmission.model_validate(await request.json())
        except (JSONDecodeError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail="raw_text is required") from exc
        return payload.raw_text, None

    if not content_type.startswith("multipart/form-data"):
        raise HTTPException(status_code=415, detail="Use application/json or multipart/form-data")
    form = await request.form()
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=422, detail="A PDF file is required")
    if upload.content_type != "application/pdf" or not (upload.filename or "").lower().endswith(
        ".pdf"
    ):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted")
    content = await upload.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller")
    path = f"{user_id}/{uuid4()}.pdf"
    try:
        await StorageService(settings).upload(
            path,
            content,
            "application/pdf",
            settings.supabase_storage_bucket_jd_uploads,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to upload PDF") from exc
    return None, path


@router.post("/parse", response_model=JDParseQueued, status_code=status.HTTP_202_ACCEPTED)
async def submit_jd(
    request: Request,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> JDParseQueued:
    raw_text, source_file_path = await _parse_submission(request, current_user.id, settings)
    description, background_job = await jd.create_submission(
        session, current_user.id, raw_text, source_file_path
    )
    queue: ArqRedis = request.app.state.arq
    try:
        queued = await queue.enqueue_job(
            "parse_jd_task",
            str(description.id),
            str(background_job.id),
            str(current_user.id),
            _job_id=str(background_job.id),
        )
        if queued is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await jd.fail_submission_enqueue(session, description, background_job)
        raise HTTPException(status_code=503, detail="Unable to enqueue JD parsing") from exc
    return JDParseQueued(job_description_id=description.id, background_job_id=background_job.id)


@router.get("", response_model=list[JDListItem])
async def list_jds(session: Session, current_user: CurrentUser) -> list[JDListItem]:
    descriptions = await jd.list_owned_jds(session, current_user.id)
    return [
        JDListItem(
            id=item.id,
            excerpt=(item.raw_text or "")[:160],
            status=item.status,
            created_at=item.created_at,
        )
        for item in descriptions
    ]


@router.get("/{jd_id}", response_model=JDDetail)
async def read_jd(jd_id: UUID, session: Session, current_user: CurrentUser) -> JDDetail:
    description = await jd.get_owned_jd(session, current_user.id, jd_id)
    if description is None:
        raise HTTPException(status_code=404, detail="Job description not found")
    requirements = await jd.get_requirements(session, jd_id) if description.status == "done" else []
    return JDDetail(
        id=description.id,
        status=description.status,
        parsed_json=(
            JDParsed.model_validate(description.parsed_json) if description.parsed_json else None
        ),
        requirements=[
            JDRequirementRead(
                id=requirement.id,
                skill=requirement.skill,
                importance=requirement.importance,
                category=requirement.category,
            )
            for requirement in requirements
        ],
    )
