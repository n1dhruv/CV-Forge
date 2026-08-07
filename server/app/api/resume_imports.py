from typing import Annotated
from uuid import UUID, uuid4

import httpx
from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.resume_import import (
    ParsedResumeImport,
    ResumeImportCommit,
    ResumeImportCommitResult,
    ResumeImportDetail,
    ResumeImportListItem,
    ResumeImportQueued,
)
from app.services import embeddings, resume_imports
from app.services.storage import StorageService

router = APIRouter(prefix="/api/resume_imports", tags=["resume-imports"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
MAX_RESUME_BYTES = 10 * 1024 * 1024
ALLOWED_FILES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("", response_model=ResumeImportQueued, status_code=status.HTTP_202_ACCEPTED)
async def submit_resume_import(
    request: Request,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeImportQueued:
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(status_code=400, detail="Upload a PDF or DOCX file")
    upload = (await request.form()).get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(status_code=400, detail="A PDF or DOCX file is required")
    filename = (upload.filename or "").lower()
    extension = next((suffix for suffix in ALLOWED_FILES if filename.endswith(suffix)), None)
    if extension is None or upload.content_type != ALLOWED_FILES[extension]:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are accepted")
    content = await upload.read(MAX_RESUME_BYTES + 1)
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be 10 MB or smaller")
    path = f"{current_user.id}/{uuid4()}{extension}"
    try:
        await StorageService(settings).upload(
            path,
            content,
            ALLOWED_FILES[extension],
            settings.supabase_storage_bucket_resume_imports,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to upload resume") from exc

    resume_import, background_job = await resume_imports.create_submission(
        session, current_user.id, path
    )
    queue: ArqRedis = request.app.state.arq
    try:
        queued = await queue.enqueue_job(
            "parse_resume_import_task",
            str(resume_import.id),
            str(background_job.id),
            str(current_user.id),
            _job_id=str(background_job.id),
        )
        if queued is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await resume_imports.fail_submission_enqueue(session, resume_import, background_job)
        raise HTTPException(status_code=503, detail="Unable to enqueue resume import") from exc
    return ResumeImportQueued(
        resume_import_id=resume_import.id, background_job_id=background_job.id
    )


@router.get("", response_model=list[ResumeImportListItem])
async def list_resume_imports(
    session: Session, current_user: CurrentUser
) -> list[ResumeImportListItem]:
    imports = await resume_imports.list_owned(session, current_user.id)
    return [
        ResumeImportListItem(
            id=item.id,
            excerpt=(item.raw_text or "")[:160],
            status=item.status,
            created_at=item.created_at,
        )
        for item in imports
    ]


@router.get("/{resume_import_id}", response_model=ResumeImportDetail)
async def read_resume_import(
    resume_import_id: UUID, session: Session, current_user: CurrentUser
) -> ResumeImportDetail:
    resume_import = await resume_imports.get_owned(session, current_user.id, resume_import_id)
    if resume_import is None:
        raise HTTPException(status_code=404, detail="Resume import not found")
    return ResumeImportDetail(
        id=resume_import.id,
        status=resume_import.status,
        parsed_json=(
            ParsedResumeImport.model_validate(resume_import.parsed_json)
            if resume_import.parsed_json
            else None
        ),
        created_at=resume_import.created_at,
        committed_at=resume_import.committed_at,
    )


@router.post("/{resume_import_id}/commit", response_model=ResumeImportCommitResult)
async def commit_resume_import(
    resume_import_id: UUID,
    payload: ResumeImportCommit,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> ResumeImportCommitResult:
    try:
        items = await resume_imports.commit_import(
            session, current_user.id, resume_import_id, payload
        )
    except resume_imports.ResumeImportNotReadyError as exc:
        raise HTTPException(status_code=409, detail="Resume import is not ready") from exc
    except resume_imports.ResumeImportAlreadyCommittedError as exc:
        raise HTTPException(status_code=409, detail="Resume import was already committed") from exc
    if items is None:
        raise HTTPException(status_code=404, detail="Resume import not found")
    queue: ArqRedis = request.app.state.arq
    await embeddings.enqueue_bullets(
        session,
        queue,
        current_user.id,
        (bullet.id for item in items for bullet in item.bullet_points),
    )
    return ResumeImportCommitResult.model_validate({"items": items})
