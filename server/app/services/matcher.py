import asyncio
import re
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
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

WORD = re.compile(r"[a-z0-9+#]+")

MIN_SIMILARITY_THRESHOLD = 0.65
STRONG_MATCH_THRESHOLD = 0.85
KEYWORD_MIN_THRESHOLD = 0.85

# Each tuple is one technology and its accepted aliases. Exact/fuzzy evidence
# for at least one technology named by a requirement is mandatory.
SPECIFIC_TECHNOLOGIES = (
    ("kafka", "apache kafka"),
    ("rabbitmq", "rabbit mq"),
    ("sqs", "amazon sqs", "aws sqs", "simple queue service"),
    ("docker",),
    ("kubernetes", "k8s"),
    ("redis",),
    ("postgresql", "postgres"),
    ("mysql",),
    ("mongodb", "mongo db"),
    ("cassandra",),
    ("java",),
    ("python",),
    ("golang", "go"),
    ("c#", "csharp"),
    ("ruby",),
    ("node js", "nodejs"),
    ("typescript",),
    ("javascript",),
    ("react", "reactjs"),
    ("graphql",),
    ("git",),
    ("github actions",),
    ("aws", "amazon web services"),
    ("azure",),
    ("gcp", "google cloud platform"),
    ("terraform",),
    ("cloudformation", "cloud formation"),
    ("prometheus",),
    ("grafana",),
    ("datadog",),
    ("elasticsearch", "elastic search", "elk", "efk"),
    ("oauth2", "oauth 2"),
    ("jwt", "json web token"),
    ("ci cd",),
)


def _normalized_text(value: str) -> str:
    return " ".join(WORD.findall(value.casefold()))


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _specific_technologies(requirement_text: str) -> tuple[tuple[str, ...], ...]:
    normalized = _normalized_text(requirement_text)
    return tuple(
        aliases
        for aliases in SPECIFIC_TECHNOLOGIES
        if any(_contains_phrase(normalized, alias) for alias in aliases)
    )


def is_specific_technology(requirement_text: str) -> bool:
    return bool(_specific_technologies(requirement_text))


def _technology_keyword_score(requirement_text: str, candidate_text: str) -> float:
    technologies = _specific_technologies(requirement_text)
    candidate = _normalized_text(candidate_text)
    if any(_contains_phrase(candidate, alias) for aliases in technologies for alias in aliases):
        return 1.0
    candidate_tokens = candidate.split()
    return max(
        (
            SequenceMatcher(None, alias.replace(" ", ""), token).ratio()
            for aliases in technologies
            for alias in aliases
            for token in candidate_tokens
        ),
        default=0.0,
    )


def _overlap(left: str, right: str) -> float:
    left_tokens = set(WORD.findall(left.casefold()))
    right_tokens = set(WORD.findall(right.casefold()))
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) if left_tokens else 0.0


def candidate_scores(
    requirement_text: str,
    candidate_text: str,
    raw_similarity: float,
    recency: float,
) -> tuple[float, float, float]:
    similarity = max(0.0, min(1.0, (raw_similarity + 1.0) / 2.0))
    keyword = (
        _technology_keyword_score(requirement_text, candidate_text)
        if is_specific_technology(requirement_text)
        else _overlap(requirement_text, candidate_text)
    )
    combined = 0.75 * similarity + 0.20 * keyword + 0.05 * recency
    return similarity, keyword, combined


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
        return MatchResult(
            jd_id=jd_id,
            pending_embeddings=False,
            requirements=[
                RequirementMatch(
                    id=requirement.id,
                    text=requirement.skill,
                    importance=requirement.importance,
                    no_match=True,
                    matched_bullets=[],
                )
                for requirement in requirements
            ],
            items=[],
        )

    bullets_by_id = {bullet.id: bullet for bullet in bullets}
    matches_by_bullet: dict[UUID, list[MatchedRequirement]] = defaultdict(list)
    bullet_ids_by_requirement: dict[UUID, list[UUID]] = defaultdict(list)
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
            _, keyword, score = candidate_scores(
                requirement.skill,
                bullet.text,
                float(match["score"]),
                _recency(bullet.item),
            )
            if is_specific_technology(requirement.skill) and keyword < KEYWORD_MIN_THRESHOLD:
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
        requirement_matches.append(
            RequirementMatch(
                id=requirement.id,
                text=requirement.skill,
                importance=requirement.importance,
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
