import asyncio
from collections import defaultdict
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
    RequirementMatch,
)
from app.services import llm_client, vector_store

SEARCH_TOP_K = 25
MIN_RERANK_SCORE = 0.0001
STRONG_RERANK_SCORE = 0.01


def _confidence(score: float) -> str | None:
    if score >= STRONG_RERANK_SCORE:
        return "strong"
    if score >= MIN_RERANK_SCORE:
        return "moderate"
    return None


def _requirement_result(
    requirement: JDRequirement, matched_bullets: list[MatchedBullet]
) -> RequirementMatch:
    technologies = list(requirement.named_technologies or [])
    return RequirementMatch(
        id=requirement.id,
        text=requirement.skill,
        importance=requirement.importance,
        named_technologies=technologies,
        technology_match_mode=requirement.technology_match_mode if technologies else None,
        technology_evidence=[],
        no_match=not matched_bullets,
        matched_bullets=matched_bullets,
    )


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

    if not requirements:
        return MatchResult(jd_id=jd_id, pending_embeddings=False, requirements=[], items=[])
    if not bullets:
        return MatchResult(
            jd_id=jd_id,
            pending_embeddings=False,
            requirements=[_requirement_result(requirement, []) for requirement in requirements],
            items=[],
        )

    bullets_by_id = {bullet.id: bullet for bullet in bullets}
    dense_ids, sparse_ids = await asyncio.to_thread(
        vector_store.vector_presence, user_id, list(bullets_by_id)
    )
    ready_ids = dense_ids & sparse_ids
    pending_embeddings = len(ready_ids) < len(bullets_by_id)
    matches_by_bullet: dict[UUID, list[MatchedRequirement]] = defaultdict(list)
    bullet_ids_by_requirement: dict[UUID, list[UUID]] = defaultdict(list)

    for requirement in requirements:
        embedding = await llm_client.get_embedding(user_id, requirement.skill)
        dense_matches, sparse_matches = await asyncio.gather(
            asyncio.to_thread(vector_store.query_dense, user_id, embedding, SEARCH_TOP_K),
            asyncio.to_thread(vector_store.query_sparse, user_id, requirement.skill, SEARCH_TOP_K),
        )
        candidate_ids: list[UUID] = []
        seen: set[UUID] = set()
        for match in dense_matches + sparse_matches:
            try:
                bullet_id = UUID(str(match["bullet_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            if (
                bullet_id in seen
                or str(bullet_id) not in ready_ids
                or bullet_id not in bullets_by_id
            ):
                continue
            seen.add(bullet_id)
            candidate_ids.append(bullet_id)

        candidates = [
            {"bullet_id": str(bullet_id), "text": bullets_by_id[bullet_id].text}
            for bullet_id in candidate_ids
        ]
        ranked = (
            await asyncio.to_thread(
                vector_store.rerank, requirement.skill, candidates, len(candidates)
            )
            if candidates
            else []
        )
        for candidate in ranked:
            score = float(candidate["score"])
            confidence = _confidence(score)
            if confidence is None:
                continue
            bullet_id = UUID(str(candidate["bullet_id"]))
            matches_by_bullet[bullet_id].append(
                MatchedRequirement(
                    id=requirement.id,
                    text=requirement.skill,
                    score=score,
                    confidence=confidence,
                    technology_evidence=[],
                )
            )
            bullet_ids_by_requirement[requirement.id].append(bullet_id)

    grouped: dict[UUID, list[MatchedBullet]] = defaultdict(list)
    matched_bullets_by_id: dict[UUID, MatchedBullet] = {}
    for bullet_id, requirement_matches in matches_by_bullet.items():
        requirement_matches.sort(key=lambda item: item.score, reverse=True)
        bullet = bullets_by_id[bullet_id]
        matched_bullet = MatchedBullet(
            id=bullet.id,
            text=bullet.text,
            score=requirement_matches[0].score,
            confidence=requirement_matches[0].confidence,
            requirements=requirement_matches,
        )
        matched_bullets_by_id[bullet_id] = matched_bullet
        grouped[bullet.item_id].append(matched_bullet)

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

    requirement_matches = []
    for requirement in requirements:
        matched_bullets = [
            matched_bullets_by_id[bullet_id]
            for bullet_id in bullet_ids_by_requirement[requirement.id]
        ]
        matched_bullets.sort(
            key=lambda bullet: next(
                match.score for match in bullet.requirements if match.id == requirement.id
            ),
            reverse=True,
        )
        requirement_matches.append(_requirement_result(requirement, matched_bullets))

    return MatchResult(
        jd_id=jd_id,
        pending_embeddings=pending_embeddings,
        requirements=requirement_matches,
        items=items,
    )
