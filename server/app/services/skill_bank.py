import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.skill_bank import BulletCreate, BulletUpdate, ItemCreate, ItemUpdate
from app.services import vector_store


async def list_items(
    session: AsyncSession, user: User, item_type: str | None
) -> list[SkillBankItem]:
    statement = select(SkillBankItem).where(SkillBankItem.user_id == user.id)
    if item_type:
        statement = statement.where(SkillBankItem.type == item_type)
    return list((await session.scalars(statement.order_by(SkillBankItem.created_at.desc()))).all())


async def get_item(session: AsyncSession, user: User, item_id: UUID) -> SkillBankItem | None:
    return await session.scalar(
        select(SkillBankItem)
        .options(selectinload(SkillBankItem.bullet_points))
        .where(SkillBankItem.id == item_id, SkillBankItem.user_id == user.id)
    )


async def create_item(session: AsyncSession, user: User, payload: ItemCreate) -> SkillBankItem:
    item = SkillBankItem(user_id=user.id, **payload.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def update_item(
    session: AsyncSession, item: SkillBankItem, payload: ItemUpdate
) -> SkillBankItem:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    if item.type != "skill":
        item.skill_category = None
    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, item: SkillBankItem) -> None:
    await asyncio.to_thread(vector_store.delete_vectors_for_item, item.user_id, item.id)
    await session.delete(item)
    await session.commit()


async def get_bullet(session: AsyncSession, user: User, bullet_id: UUID) -> BulletPoint | None:
    return await session.scalar(
        select(BulletPoint)
        .join(SkillBankItem, BulletPoint.item_id == SkillBankItem.id)
        .where(BulletPoint.id == bullet_id, SkillBankItem.user_id == user.id)
    )


async def create_bullet(
    session: AsyncSession, item: SkillBankItem, payload: BulletCreate
) -> BulletPoint:
    bullet = BulletPoint(item_id=item.id, **payload.model_dump())
    session.add(bullet)
    await session.commit()
    await session.refresh(bullet)
    return bullet


async def update_bullet(
    session: AsyncSession, bullet: BulletPoint, payload: BulletUpdate
) -> BulletPoint:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(bullet, field, value)
    await session.commit()
    await session.refresh(bullet)
    return bullet


async def delete_bullet(session: AsyncSession, user_id: UUID, bullet: BulletPoint) -> None:
    await asyncio.to_thread(vector_store.delete_vectors, user_id, bullet.id)
    await session.delete(bullet)
    await session.commit()
