from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.jobs import BackgroundJobRead
from app.services import jobs

router = APIRouter(prefix="/api/background_jobs", tags=["background-jobs"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/{job_id}", response_model=BackgroundJobRead)
async def read_background_job(
    job_id: UUID, session: Session, current_user: CurrentUser
) -> BackgroundJobRead:
    job = await jobs.get_owned_job(session, current_user.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Background job not found")
    return BackgroundJobRead(status=job.status, result=job.result, error=job.error)
