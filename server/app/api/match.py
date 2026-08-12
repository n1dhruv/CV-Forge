from typing import Annotated
from uuid import UUID

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.match import MatchQueued
from app.services import matcher

router = APIRouter(prefix="/api/match", tags=["matching"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/{jd_id}", response_model=MatchQueued, status_code=status.HTTP_202_ACCEPTED)
async def match_job_description(
    jd_id: UUID, request: Request, session: Session, current_user: CurrentUser
) -> MatchQueued:
    job = await matcher.create_match_job(session, current_user.id, jd_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Completed job description not found")
    queue: ArqRedis = request.app.state.arq
    try:
        queued = await queue.enqueue_job(
            "match_jd_task",
            str(jd_id),
            str(job.id),
            str(current_user.id),
            _job_id=str(job.id),
        )
        if queued is None:
            raise RuntimeError("Job ID already exists")
    except Exception as exc:
        await matcher.fail_match_enqueue(session, job)
        raise HTTPException(status_code=503, detail="Unable to enqueue matching") from exc
    return MatchQueued(jd_id=jd_id, background_job_id=job.id)
