import asyncio
import re
from collections import defaultdict
from datetime import date
from typing import Literal
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
from app.services.technology_matching import (
    infer_legacy_named_technologies,
    technology_keyword_score,
)

WORD = re.compile(r"[a-z0-9+#]+")

MIN_SIMILARITY_THRESHOLD = 0.65
STRONG_MATCH_THRESHOLD = 0.85
KEYWORD_MIN_THRESHOLD = 0.85


def _overlap(left: str, right: str) -> float:
    left_tokens = set(WORD.findall(left.casefold()))
    right_tokens = set(WORD.findall(right.casefold()))
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens else 0.0


def candidate_scores(
    requirement_text: str,
    candidate_text: str,
    raw_similarity: float,
    recency: float,
    named_technologies: list[str] | tuple[str, ...] | None = None,
    technology_match_mode: Literal["any", "all"] = "any",
) -> tuple[float, float, float, list[str]]:
    similarity = max(0.0, min(1.0, (raw_similarity + 1.0) / 2.0))
    technologies = (
        infer_legacy_named_technologies(requirement_text)
        if named_technologies is None
        else list(named_technologies)
    )
    if technologies:
        keyword, evidence = technology_keyword_score(
            technologies,
            candidate_text,
            technology_match_mode,
            KEYWORD_MIN_THRESHOLD,
        )
    else:
        keyword, evidence = _overlap(requirement_text, candidate_text), []
    combined = 0.75 * similarity + 0.20 * keyword + 0.05 * recency
    return similarity, keyword, combined, evidence


def is_specific_technology(
    requirement_text: str, named_technologies: list[str] | None = None
) -> bool:
    technologies = (
        infer_legacy_named_technologies(requirement_text)
        if named_technologies is None
        else named_technologies
    )
    return bool(technologies)


def _technology_config(
    requirement: JDRequirement,
) -> tuple[list[str], Literal["any", "all"]]:
    technologies = requirement.named_technologies
    if technologies is None:
        technologies = infer_legacy_named_technologies(requirement.skill)
    match_mode = requirement.technology_match_mode
    return list(technologies), match_mode if match_mode in ("any", "all") else "any"


def _confidence(score: float) -> str | None:
    if score >= STRONG_MATCH_THRESHOLD:
        return "strong"
    if score >= MIN_SIMILARITY_THRESHOLD:
        return "moderate"
    return None


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

    if not requirements:
        return MatchResult(jd_id=jd_id, pending_embeddings=False, requirements=[], items=[])
    if not bullets:
        requirement_matches = []
        for requirement in requirements:
            technologies, technology_match_mode = _technology_config(requirement)
            requirement_matches.append(
                RequirementMatch(
                    id=requirement.id,
                    text=requirement.skill,
                    importance=requirement.importance,
                    named_technologies=technologies,
                    technology_match_mode=(technology_match_mode if technologies else None),
                    technology_evidence=[],
                    no_match=True,
                    matched_bullets=[],
                )
            )
        return MatchResult(
            jd_id=jd_id,
            pending_embeddings=False,
            requirements=requirement_matches,
            items=[],
        )

    bullets_by_id = {bullet.id: bullet for bullet in bullets}
    matches_by_bullet: dict[UUID, list[MatchedRequirement]] = defaultdict(list)
    bullet_ids_by_requirement: dict[UUID, list[UUID]] = defaultdict(list)
    evidence_by_requirement: dict[UUID, set[str]] = defaultdict(set)
    seen_vector_ids: set[UUID] = set()
    for requirement in requirements:
        technologies, technology_match_mode = _technology_config(requirement)
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
            _, keyword, score, technology_evidence = candidate_scores(
                requirement.skill,
                bullet.text,
                float(match["score"]),
                _recency(bullet.item),
                technologies,
                technology_match_mode,
            )
            if technologies and keyword < KEYWORD_MIN_THRESHOLD:
                continue
            confidence = _confidence(score)
            if confidence is None:
                continue
            matches_by_bullet[bullet_id].append(
                MatchedRequirement(
                    id=requirement.id,
                    text=requirement.skill,
                    score=score,
                    confidence=confidence,
                    technology_evidence=technology_evidence,
                )
            )
            bullet_ids_by_requirement[requirement.id].append(bullet_id)
            evidence_by_requirement[requirement.id].update(technology_evidence)

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
        technologies, technology_match_mode = _technology_config(requirement)
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
        requirement_matches.append(
            RequirementMatch(
                id=requirement.id,
                text=requirement.skill,
                importance=requirement.importance,
                named_technologies=technologies,
                technology_match_mode=(technology_match_mode if technologies else None),
                technology_evidence=[
                    technology
                    for technology in technologies
                    if technology in evidence_by_requirement[requirement.id]
                ],
                no_match=not matched_bullets,
                matched_bullets=matched_bullets,
            )
        )
    return MatchResult(
        jd_id=jd_id,
        pending_embeddings=len(seen_vector_ids) < len(bullets_by_id),
        requirements=requirement_matches,
        items=items,
    )
