from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.profile import ProfileRead, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("", response_model=ProfileRead)
async def read_profile(current_user: CurrentUser) -> ProfileRead:
    return ProfileRead.from_user(current_user)


@router.put("", response_model=ProfileRead)
async def update_profile(
    payload: ProfileUpdate, session: Session, current_user: CurrentUser
) -> ProfileRead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await session.commit()
    await session.refresh(current_user)
    return ProfileRead.from_user(current_user)
