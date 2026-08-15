from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from arq.connections import ArqRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import get_db_session
from app.schemas.skill_bank import (
    BulletCreate,
    BulletRead,
    BulletUpdate,
    ItemCreate,
    ItemDetail,
    ItemLink,
    ItemRead,
    ItemType,
    ItemUpdate,
    ReembedQueued,
    validate_item_links,
)
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import embeddings, skill_bank

router = APIRouter(prefix="/api/skill_bank", tags=["skill-bank"])
Session = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/items", response_model=list[ItemRead])
async def list_skill_bank_items(
    session: Session,
    current_user: CurrentUser,
    item_type: Annotated[ItemType | None, Query(alias="type")] = None,
) -> list[ItemRead]:
    return await skill_bank.list_items(session, current_user, item_type)  # type: ignore[return-value]


@router.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_skill_bank_item(
    payload: ItemCreate, request: Request, session: Session, current_user: CurrentUser
) -> ItemRead:
    item = await skill_bank.create_item(session, current_user, payload)
    queue: ArqRedis = request.app.state.arq
    await embeddings.enqueue_items(session, queue, current_user.id, [item.id])
    return item  # type: ignore[return-value]


@router.post(
    "/items/reembed", response_model=ReembedQueued, status_code=status.HTTP_202_ACCEPTED
)
async def reembed_all(
    request: Request, session: Session, current_user: CurrentUser
) -> ReembedQueued:
    item_ids = list(
        (
            await session.scalars(
                select(SkillBankItem.id).where(SkillBankItem.user_id == current_user.id)
            )
        ).all()
    )
    bullet_ids = list(
        (
            await session.scalars(
                select(BulletPoint.id)
                .join(SkillBankItem)
                .where(SkillBankItem.user_id == current_user.id)
            )
        ).all()
    )
    queue: ArqRedis = request.app.state.arq
    items_queued = await embeddings.enqueue_items(session, queue, current_user.id, item_ids)
    bullets_queued = await embeddings.enqueue_bullets(session, queue, current_user.id, bullet_ids)
    return ReembedQueued(
        items_queued=items_queued,
        bullets_queued=bullets_queued,
        failed=len(item_ids) + len(bullet_ids) - items_queued - bullets_queued,
    )


async def owned_item_or_404(session: AsyncSession, current_user: CurrentUser, item_id: UUID):
    item = await skill_bank.get_item(session, current_user, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Skill bank item not found")
    return item


@router.get("/items/{item_id}", response_model=ItemDetail)
async def read_skill_bank_item(
    item_id: UUID, session: Session, current_user: CurrentUser
) -> ItemDetail:
    return await owned_item_or_404(session, current_user, item_id)


@router.put("/items/{item_id}", response_model=ItemRead)
async def update_skill_bank_item(
    item_id: UUID,
    payload: ItemUpdate,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> ItemRead:
    item = await owned_item_or_404(session, current_user, item_id)
    try:
        validate_item_links(
            payload.type or item.type,
            payload.links
            if payload.links is not None
            else [ItemLink.model_validate(link) for link in (item.links or [])],
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    bullet_ids = [bullet.id for bullet in item.bullet_points]
    updated = await skill_bank.update_item(session, item, payload)
    queue: ArqRedis = request.app.state.arq
    await embeddings.enqueue_items(session, queue, current_user.id, [item.id])
    await embeddings.enqueue_bullets(session, queue, current_user.id, bullet_ids)
    return updated  # type: ignore[return-value]


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill_bank_item(
    item_id: UUID, session: Session, current_user: CurrentUser
) -> Response:
    item = await owned_item_or_404(session, current_user, item_id)
    await skill_bank.delete_item(session, item)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/items/{item_id}/bullets", response_model=BulletRead, status_code=status.HTTP_201_CREATED
)
async def create_bullet(
    item_id: UUID,
    payload: BulletCreate,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> BulletRead:
    item = await owned_item_or_404(session, current_user, item_id)
    bullet = await skill_bank.create_bullet(session, item, payload)
    queue: ArqRedis = request.app.state.arq
    await embeddings.enqueue_bullets(session, queue, current_user.id, [bullet.id])
    return bullet  # type: ignore[return-value]


async def owned_bullet_or_404(session: AsyncSession, current_user: CurrentUser, bullet_id: UUID):
    bullet = await skill_bank.get_bullet(session, current_user, bullet_id)
    if bullet is None:
        raise HTTPException(status_code=404, detail="Bullet point not found")
    return bullet


@router.put("/bullets/{bullet_id}", response_model=BulletRead)
async def update_bullet(
    bullet_id: UUID,
    payload: BulletUpdate,
    request: Request,
    session: Session,
    current_user: CurrentUser,
) -> BulletRead:
    bullet = await owned_bullet_or_404(session, current_user, bullet_id)
    updated = await skill_bank.update_bullet(session, bullet, payload)
    queue: ArqRedis = request.app.state.arq
    await embeddings.enqueue_bullets(session, queue, current_user.id, [bullet.id])
    return updated  # type: ignore[return-value]


@router.delete("/bullets/{bullet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bullet(bullet_id: UUID, session: Session, current_user: CurrentUser) -> Response:
    bullet = await owned_bullet_or_404(session, current_user, bullet_id)
    await skill_bank.delete_bullet(session, current_user.id, bullet)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
