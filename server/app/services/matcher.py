import asyncio
import re
from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.schemas.match import (
    MatchResult,
    MatchedBullet,
    MatchedItem,
    MatchedRequirement,
)
from app.services import llm_client, vector_store

WORD = re.compile(r"[a-z0-9+#.]+")


def _overlap(left: str, right: str) -> float:
    left_tokens = set(WORD.findall(left.casefold()))
    right_tokens = set(WORD.findall(right.casefold()))
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens else 0.0


def _recency(item: SkillBankItem) -> float:
    item_date = item.end_date or item.start_date
    if item_date is None:
        return 0.0
    years = max(0.0, (date.today() - item_date).days / 365.25)
    return max(0.0, 1.0 - years / 10.0)


async def match_jd(user_id: UUID, jd_id: UUID, max_bullets_per_item: int = 4) -> MatchResult | None:
    async with async_session_factory() as session:
        description = await session.scalar(
            select(JobDescription).where(
                JobDescription.id == jd_id, JobDescription.user_id == user_id
            )
        )
        if description is None:
            return None
        requirements = list(
            (await session.scalars(select(JDRequirement).where(JDRequirement.jd_id == jd_id))).all()
        )
        bullets = list(
            (
                await session.scalars(
                    select(BulletPoint)
                    .join(SkillBankItem)
                    .options(selectinload(BulletPoint.item))
                    .where(SkillBankItem.user_id == user_id)
                )
            ).all()
        )

    if not requirements or not bullets:
        return MatchResult(jd_id=jd_id, pending_embeddings=False, items=[])

    bullets_by_id = {bullet.id: bullet for bullet in bullets}
    matches_by_bullet: dict[UUID, list[MatchedRequirement]] = defaultdict(list)
    seen_vector_ids: set[UUID] = set()
    for requirement in requirements:
        embedding = await llm_client.get_embedding(user_id, requirement.skill)
        matches = await asyncio.to_thread(
            vector_store.query_similar,
            user_id,
            embedding,
            len(bullets),
        )
        for match in matches:
            try:
                bullet_id = UUID(str(match["bullet_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            bullet = bullets_by_id.get(bullet_id)
            if bullet is None:
                continue
            seen_vector_ids.add(bullet_id)
            semantic = max(0.0, min(1.0, (float(match["score"]) + 1.0) / 2.0))
            score = 0.75 * semantic + 0.20 * _overlap(requirement.skill, bullet.text)
            score += 0.05 * _recency(bullet.item)
            matches_by_bullet[bullet_id].append(
                MatchedRequirement(id=requirement.id, text=requirement.skill, score=score)
            )

    grouped: dict[UUID, list[MatchedBullet]] = defaultdict(list)
    for bullet_id, requirement_matches in matches_by_bullet.items():
        requirement_matches.sort(key=lambda item: item.score, reverse=True)
        bullet = bullets_by_id[bullet_id]
        grouped[bullet.item_id].append(
            MatchedBullet(
                id=bullet.id,
                text=bullet.text,
                score=requirement_matches[0].score,
                requirements=requirement_matches,
            )
        )

    items = []
    for item_id, matched_bullets in grouped.items():
        matched_bullets.sort(key=lambda bullet: bullet.score, reverse=True)
        item = bullets_by_id[matched_bullets[0].id].item
        items.append(
            MatchedItem(
                id=item_id,
                type=item.type,
                title=item.title,
                org=item.org,
                start_date=item.start_date,
                end_date=item.end_date,
                bullets=matched_bullets[:max_bullets_per_item],
            )
        )
    items.sort(key=lambda item: item.bullets[0].score, reverse=True)
    return MatchResult(
        jd_id=jd_id,
        pending_embeddings=len(seen_vector_ids) < len(bullets_by_id),
        items=items,
    )
