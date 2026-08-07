"""Print every Pinecone candidate score for a real JD requirement.

Run from ``server/``. Without ``--jd-id``, the latest JD containing a
Kafka/RabbitMQ/SQS requirement is selected.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import llm_client, vector_store
from app.services.matcher import (
    KEYWORD_MIN_THRESHOLD,
    MIN_SIMILARITY_THRESHOLD,
    STRONG_MATCH_THRESHOLD,
    _recency,
    candidate_scores,
    is_specific_technology,
    match_jd,
)


async def inspect(
    jd_id: UUID | None,
    requirement_filter: str | None,
    top_k: int,
    verify_result: bool,
) -> None:
    async with async_session_factory() as session:
        if jd_id is None:
            row = (
                await session.execute(
                    select(JDRequirement, JobDescription)
                    .join(JobDescription, JobDescription.id == JDRequirement.jd_id)
                    .where(
                        or_(
                            JDRequirement.skill.ilike("%kafka%"),
                            JDRequirement.skill.ilike("%rabbitmq%"),
                            JDRequirement.skill.ilike("%sqs%"),
                        )
                    )
                    .order_by(JobDescription.created_at.desc())
                    .limit(1)
                )
            ).first()
            if row is None:
                raise SystemExit("No Kafka/RabbitMQ/SQS requirement found; pass --jd-id.")
            jd_id = row.JDRequirement.jd_id
            description = row.JobDescription
        else:
            description = await session.scalar(
                select(JobDescription).where(JobDescription.id == jd_id)
            )
            if description is None:
                raise SystemExit(f"JD {jd_id} was not found.")

        requirements = list(
            (await session.scalars(select(JDRequirement).where(JDRequirement.jd_id == jd_id))).all()
        )
        if requirement_filter:
            needle = requirement_filter.casefold()
            requirements = [item for item in requirements if needle in item.skill.casefold()]
        bullets = list(
            (
                await session.scalars(
                    select(BulletPoint)
                    .join(SkillBankItem)
                    .options(selectinload(BulletPoint.item))
                    .where(SkillBankItem.user_id == description.user_id)
                )
            ).all()
        )

    bullets_by_id = {bullet.id: bullet for bullet in bullets}
    print(f"jd_id={jd_id} user_id={description.user_id} bullets={len(bullets)}")
    for requirement in requirements:
        print(f"\nREQUIREMENT: {requirement.skill}")
        embedding = await llm_client.get_embedding(description.user_id, requirement.skill)
        matches = await asyncio.to_thread(
            vector_store.query_similar,
            description.user_id,
            embedding,
            min(top_k, len(bullets)),
        )
        for rank, match in enumerate(matches, start=1):
            try:
                bullet = bullets_by_id[UUID(str(match["bullet_id"]))]
            except (KeyError, TypeError, ValueError):
                continue
            raw_similarity = float(match["score"])
            recency = _recency(bullet.item)
            similarity, keyword, combined = candidate_scores(
                requirement.skill, bullet.text, raw_similarity, recency
            )
            named_technology = is_specific_technology(requirement.skill)
            if named_technology and keyword < KEYWORD_MIN_THRESHOLD:
                decision = "rejected:keyword"
            elif combined < MIN_SIMILARITY_THRESHOLD:
                decision = "rejected:similarity"
            elif combined >= STRONG_MATCH_THRESHOLD:
                decision = "accepted:strong"
            else:
                decision = "accepted:moderate"
            print(
                f"{rank:>2}. raw={raw_similarity:.4f} similarity={similarity:.4f} "
                f"keyword={keyword:.4f} recency={recency:.4f} combined={combined:.4f} "
                f"named_technology={named_technology} {decision}"
            )
            print(f"    {bullet.text}")

    if verify_result:
        result = await match_jd(description.user_id, jd_id)
        if result is None:
            raise SystemExit("Matcher unexpectedly returned no owned JD.")
        selected = result.requirements
        if requirement_filter:
            needle = requirement_filter.casefold()
            selected = [item for item in selected if needle in item.text.casefold()]
        for requirement in selected:
            print(
                f"\nFINAL: {requirement.text} no_match={requirement.no_match} "
                f"matched_bullets={len(requirement.matched_bullets)}"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jd-id", type=UUID)
    parser.add_argument("--requirement", help="case-insensitive requirement substring")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--verify-result", action="store_true", help="also run match_jd")
    args = parser.parse_args()
    asyncio.run(inspect(args.jd_id, args.requirement, max(1, args.top_k), args.verify_result))


if __name__ == "__main__":
    main()
