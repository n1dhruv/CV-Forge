import asyncio
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.jobs import BackgroundJob
from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import SkillBankItem
from app.schemas.match import (
    MatchResult,
    MatchedBullet,
    MatchedItem,
    MatchedRequirement,
    RequirementMatch,
)
from app.services import embeddings, llm_client, vector_store

SEARCH_TOP_K = 25
MIN_RERANK_SCORE = 0.0001
STRONG_RERANK_SCORE = 0.01


async def create_match_job(
    session: AsyncSession, user_id: UUID, jd_id: UUID
) -> BackgroundJob | None:
    description = await session.scalar(
        select(JobDescription).where(
            JobDescription.id == jd_id,
            JobDescription.user_id == user_id,
            JobDescription.status == "done",
        )
    )
    if description is None:
        return None
    job = BackgroundJob(
        user_id=user_id,
        job_type="match",
        status="queued",
        result={"jd_id": str(jd_id)},
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def fail_match_enqueue(session: AsyncSession, job: BackgroundJob) -> None:
    job.status = "failed"
    job.error = "Unable to enqueue matching — try again"
    await session.commit()


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
        items = list(
            (
                await session.scalars(
                    select(SkillBankItem)
                    .options(selectinload(SkillBankItem.bullet_points))
                    .where(SkillBankItem.user_id == user_id)
                )
            ).all()
        )

    if not requirements:
        return MatchResult(jd_id=jd_id, pending_embeddings=False, requirements=[], items=[])
    if not items:
        return MatchResult(
            jd_id=jd_id,
            pending_embeddings=False,
            requirements=[_requirement_result(requirement, []) for requirement in requirements],
            items=[],
        )

    items_by_id = {item.id: item for item in items}
    bullets_by_id = {bullet.id: bullet for item in items for bullet in item.bullet_points}
    record_ids = [*bullets_by_id, *items_by_id]
    dense_ids, sparse_ids = await asyncio.to_thread(
        vector_store.vector_presence, user_id, record_ids
    )
    ready_ids = dense_ids & sparse_ids
    pending_embeddings = any(str(record_id) not in ready_ids for record_id in record_ids)
    matches_by_source: dict[tuple[str, UUID], list[MatchedRequirement]] = defaultdict(list)
    source_ids_by_requirement: dict[UUID, list[tuple[str, UUID]]] = defaultdict(list)

    for requirement in requirements:
        embedding = await llm_client.get_embedding(user_id, requirement.skill)
        dense_matches, sparse_matches = await asyncio.gather(
            asyncio.to_thread(vector_store.query_dense, user_id, embedding, SEARCH_TOP_K),
            asyncio.to_thread(vector_store.query_sparse, user_id, requirement.skill, SEARCH_TOP_K),
        )
        candidates = []
        seen: set[tuple[str, UUID]] = set()
        for match in dense_matches + sparse_matches:
            level = str(match.get("level") or match.get("metadata", {}).get("level", "bullet"))
            try:
                record_id = UUID(str(match["item_id"] if level == "item" else match["bullet_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            source = (level, record_id)
            if source in seen or str(record_id) not in ready_ids:
                continue
            if level == "item":
                item = items_by_id.get(record_id)
                if item is None:
                    continue
                text = embeddings.item_text(item)
                item_id = item.id
            else:
                bullet = bullets_by_id.get(record_id)
                if bullet is None:
                    continue
                text = bullet.text
                item_id = bullet.item_id
                level = "bullet"
                source = (level, record_id)
            seen.add(source)
            candidates.append(
                {
                    "candidate_id": f"{level}:{record_id}",
                    "level": level,
                    "record_id": str(record_id),
                    "item_id": str(item_id),
                    "text": text,
                }
            )
        ranked = (
            await asyncio.to_thread(
                vector_store.rerank, requirement.skill, candidates, len(candidates)
            )
            if candidates
            else []
        )
        accepted = []
        for candidate in ranked:
            score = float(candidate["score"])
            confidence = _confidence(score)
            if confidence is None:
                continue
            accepted.append({**candidate, "score": score, "confidence": confidence})

        by_item: dict[str, list[dict]] = defaultdict(list)
        for candidate in accepted:
            by_item[candidate["item_id"]].append(candidate)
        deduplicated = []
        for item_candidates in by_item.values():
            if {candidate["level"] for candidate in item_candidates} == {"item", "bullet"}:
                deduplicated.append(max(item_candidates, key=lambda candidate: candidate["score"]))
            else:
                deduplicated.extend(item_candidates)

        for candidate in deduplicated:
            source = (candidate["level"], UUID(candidate["record_id"]))
            matches_by_source[source].append(
                MatchedRequirement(
                    id=requirement.id,
                    text=requirement.skill,
                    score=candidate["score"],
                    confidence=candidate["confidence"],
                    technology_evidence=[],
                )
            )
            source_ids_by_requirement[requirement.id].append(source)

    grouped: dict[UUID, list[MatchedBullet]] = defaultdict(list)
    matched_by_source: dict[tuple[str, UUID], MatchedBullet] = {}
    for source, requirement_matches in matches_by_source.items():
        requirement_matches.sort(key=lambda item: item.score, reverse=True)
        level, record_id = source
        if level == "item":
            item = items_by_id[record_id]
            text = embeddings.item_text(item)
            item_id = item.id
        else:
            bullet = bullets_by_id[record_id]
            text = bullet.text
            item_id = bullet.item_id
        matched_bullet = MatchedBullet(
            bullet_point_id=record_id if level == "bullet" else None,
            skill_bank_item_id=record_id if level == "item" else None,
            text=text,
            score=requirement_matches[0].score,
            confidence=requirement_matches[0].confidence,
            requirements=requirement_matches,
        )
        matched_by_source[source] = matched_bullet
        grouped[item_id].append(matched_bullet)

    items = []
    for item_id, matched_bullets in grouped.items():
        matched_bullets.sort(key=lambda bullet: bullet.score, reverse=True)
        item = items_by_id[item_id]
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
            matched_by_source[source] for source in source_ids_by_requirement[requirement.id]
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
