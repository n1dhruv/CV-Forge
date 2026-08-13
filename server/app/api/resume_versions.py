from typing import Annotated
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.resume_version import (
    ResumeBulletSelectionRead,
    ResumeBulletSelectionUpdate,
    ResumeVersionCreate,
    ResumeOperationQueued,
    ResumeTexUpdate,
    ResumeVersionDetail,
    ResumeVersionHistoryItem,
    ResumeFamilyRead,
    ResumeMetadataUpdate,
    ResumeVersionListItem,
    ResumeVersionRead,
    RewriteQueued,
    RewriteRequest,
)
from app.services import resume_versions, rewriter
from app.services.storage import StorageService

router = APIRouter(tags=["resume-versions"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/api/resume_versions", response_model=list[ResumeFamilyRead])
async def list_resume_families(session: Session, current_user: CurrentUser) -> list[ResumeFamilyRead]:
    families = await resume_versions.list_families(session, current_user.id)
    return [
        ResumeFamilyRead(
            id=root.id,
            name=root.name,
            versions=[
                ResumeVersionListItem(
                    id=version.id,
                    parent_version_id=version.parent_version_id,
                    status=version.status,
                    name=version.name,
                    version_label=version.version_label,
                    created_at=version.created_at,
                    has_pdf=bool(version.pdf_storage_path),
                )
                for version in versions
            ],
        )
        for root, versions in families
    ]


@router.post(
    "/api/resume_versions", response_model=ResumeVersionRead, status_code=status.HTTP_201_CREATED
)
async def create_resume_version(
    payload: ResumeVersionCreate, session: Session, current_user: CurrentUser
) -> ResumeVersionRead:
    version = await resume_versions.create(session, current_user.id, payload.jd_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Job description not found")
    return ResumeVersionRead.model_validate(version)


@router.post(
    "/api/resume_versions/{version_id}/rewrite",
    response_model=RewriteQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_rewrite(
    version_id: UUID,
    payload: RewriteRequest,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> RewriteQueued:
    try:
        queued = await resume_versions.queue_rewrite(
            session, current_user.id, version_id, payload.bullet_point_ids
        )
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(status_code=409, detail="Resume version is not a draft") from exc
    except resume_versions.InvalidBulletSelectionError as exc:
        raise HTTPException(status_code=404, detail="One or more bullets were not found") from exc
    if queued is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    version, job = queued
    queue: ArqRedis = request.app.state.arq
    try:
        result = await queue.enqueue_job(
            "rewrite_bullets_task",
            str(version.id),
            str(job.id),
            str(current_user.id),
            [str(value) for value in payload.bullet_point_ids],
            _job_id=str(job.id),
        )
        if result is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await resume_versions.fail_enqueue(session, version, job)
        raise HTTPException(status_code=503, detail="Unable to enqueue rewrite") from exc
    return RewriteQueued(resume_version_id=version.id, background_job_id=job.id)


@router.post(
    "/api/resume_versions/{version_id}/assemble",
    response_model=ResumeOperationQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def assemble_resume_version(
    version_id: UUID,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> ResumeOperationQueued:
    try:
        queued = await resume_versions.queue_assembly(session, current_user.id, version_id)
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(status_code=409, detail="Resume version is not finalized") from exc
    if queued is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    version, job, created = queued
    if not created:
        return ResumeOperationQueued(resume_version_id=version.id, background_job_id=job.id)
    try:
        result = await request.app.state.arq.enqueue_job(
            "assemble_resume_task",
            str(version.id),
            str(job.id),
            str(current_user.id),
            _job_id=str(job.id),
        )
        if result is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await resume_versions.fail_operation_enqueue(session, version, job, "finalized")
        raise HTTPException(status_code=503, detail="Unable to enqueue resume assembly") from exc
    return ResumeOperationQueued(resume_version_id=version.id, background_job_id=job.id)


@router.post(
    "/api/resume_versions/{version_id}/compile",
    response_model=ResumeOperationQueued,
    status_code=status.HTTP_202_ACCEPTED,
)
async def compile_resume_version(
    version_id: UUID,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> ResumeOperationQueued:
    try:
        queued = await resume_versions.queue_compile(session, current_user.id, version_id)
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(
            status_code=409, detail="Resume source is not ready to compile"
        ) from exc
    if queued is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    version, job, created = queued
    if not created:
        return ResumeOperationQueued(resume_version_id=version.id, background_job_id=job.id)
    previous_status = str(job.result["previous_status"])
    try:
        result = await request.app.state.arq.enqueue_job(
            "compile_resume_task",
            str(version.id),
            str(job.id),
            str(current_user.id),
            _job_id=str(job.id),
        )
        if result is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await resume_versions.fail_operation_enqueue(session, version, job, previous_status)
        raise HTTPException(status_code=503, detail="Unable to enqueue resume compilation") from exc
    return ResumeOperationQueued(resume_version_id=version.id, background_job_id=job.id)


async def _version_detail(version: object, settings: Settings) -> ResumeVersionDetail:
    data = ResumeVersionDetail.model_validate(version)
    if data.pdf_download_url is None and getattr(version, "pdf_storage_path", None):
        try:
            signed = await StorageService(settings).signed_download_url(version.pdf_storage_path)
        except (httpx.HTTPError, KeyError) as exc:
            raise HTTPException(
                status_code=502, detail="Unable to create PDF download URL"
            ) from exc
        data.pdf_download_url = str(signed["signed_url"])
    return data


@router.get("/api/resume_versions/{version_id}", response_model=ResumeVersionDetail)
async def read_resume_version(
    version_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeVersionDetail:
    version = await resume_versions.get_owned(session, current_user.id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return await _version_detail(version, settings)


@router.put("/api/resume_versions/{version_id}/tex", response_model=ResumeVersionDetail)
async def update_resume_tex(
    version_id: UUID,
    payload: ResumeTexUpdate,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeVersionDetail:
    try:
        version = await resume_versions.update_tex(
            session, current_user.id, version_id, payload.tex_source
        )
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(status_code=409, detail="Resume version cannot be edited now") from exc
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return await _version_detail(version, settings)


@router.put("/api/resume_versions/{version_id}/metadata", response_model=ResumeVersionDetail)
async def update_resume_metadata(
    version_id: UUID,
    payload: ResumeMetadataUpdate,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeVersionDetail:
    version = await resume_versions.update_metadata(
        session, current_user.id, version_id, payload.name, payload.version_label
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return await _version_detail(version, settings)


@router.post(
    "/api/resume_versions/{version_id}/versions",
    response_model=ResumeVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_snapshot(
    version_id: UUID,
    session: Session,
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeVersionDetail:
    try:
        version = await resume_versions.create_snapshot(session, current_user.id, version_id)
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(status_code=409, detail="Resume version cannot be copied now") from exc
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return await _version_detail(version, settings)


@router.get(
    "/api/resume_versions/{version_id}/history",
    response_model=list[ResumeVersionHistoryItem],
)
async def read_resume_history(
    version_id: UUID, session: Session, current_user: CurrentUser
) -> list[ResumeVersionHistoryItem]:
    versions = await resume_versions.history(session, current_user.id, version_id)
    if versions is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return [
        ResumeVersionHistoryItem(
            id=version.id,
            parent_version_id=version.parent_version_id,
            status=version.status,
            created_at=version.created_at,
            has_pdf=bool(version.pdf_storage_path),
            name=version.name,
            version_label=version.version_label,
        )
        for version in versions
    ]


@router.get(
    "/api/resume_versions/{version_id}/bullets",
    response_model=list[ResumeBulletSelectionRead],
)
async def list_resume_bullets(
    version_id: UUID, session: Session, current_user: CurrentUser
) -> list[ResumeBulletSelectionRead]:
    bullets = await resume_versions.list_bullets(session, current_user.id, version_id)
    if bullets is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return [ResumeBulletSelectionRead.model_validate(bullet) for bullet in bullets]


@router.put(
    "/api/resume_bullet_selections/{selection_id}",
    response_model=ResumeBulletSelectionRead,
)
async def update_resume_bullet(
    selection_id: UUID,
    payload: ResumeBulletSelectionUpdate,
    session: Session,
    current_user: CurrentUser,
) -> ResumeBulletSelectionRead:
    owned = await resume_versions.get_selection_owned(session, current_user.id, selection_id)
    if owned is None:
        raise HTTPException(status_code=404, detail="Resume bullet selection not found")
    selection, version = owned
    if version.status != "reviewing":
        raise HTTPException(status_code=409, detail="Resume bullets can only change during review")

    if payload.revert:
        selection.rewritten_text = selection.original_text
        selection.approved = False
        selection.resolved = True
        selection.flagged_terms = []
        selection.low_effort_rewrite = False
    else:
        if payload.rewritten_text is not None:
            if rewriter.number_tokens(payload.rewritten_text) != rewriter.number_tokens(
                selection.original_text
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Edited text must preserve every number and metric exactly",
                )
            selection.rewritten_text = payload.rewritten_text
            selection.approved = False
            selection.resolved = False
            selection.low_effort_rewrite = False
            selection.flagged_terms = [
                flag
                for flag in selection.flagged_terms
                if flag.get("reason") == "new_technology"
                and rewriter.contains_term(payload.rewritten_text, flag.get("term", ""))
            ]
        if payload.approved is not None:
            selection.approved = payload.approved
            selection.resolved = payload.approved
    await session.commit()
    await session.refresh(selection)
    return ResumeBulletSelectionRead.model_validate(selection)


@router.post("/api/resume_versions/{version_id}/finalize", response_model=ResumeVersionRead)
async def finalize_resume_version(
    version_id: UUID, session: Session, current_user: CurrentUser
) -> ResumeVersionRead:
    try:
        result = await resume_versions.finalize(session, current_user.id, version_id)
    except resume_versions.InvalidResumeVersionStateError as exc:
        raise HTTPException(
            status_code=409, detail="Resume version is not ready for review"
        ) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    version, unresolved = result
    if unresolved or version.status != "finalized":
        raise HTTPException(
            status_code=409,
            detail=(
                "Every bullet must be approved or reverted before finalizing. "
                f"Unresolved selection IDs: {', '.join(str(value) for value in unresolved)}"
            ),
        )
    return ResumeVersionRead.model_validate(version)
