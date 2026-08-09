from datetime import date
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import match as match_api
from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.services import llm_client, matcher, vector_store


class Result:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, description, requirements, bullets):
        self.description = description
        self.results = iter([requirements, bullets])

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def scalar(self, statement):
        del statement
        return self.description

    async def scalars(self, statement):
        del statement
        return Result(next(self.results))


def rows(user_id, requirement_text, bullet_texts):
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text=requirement_text, status="done")
    requirement = JDRequirement(
        id=uuid4(), jd_id=jd.id, skill=requirement_text, importance="required"
    )
    bullets = []
    for index, text in enumerate(bullet_texts):
        item = SkillBankItem(
            id=uuid4(),
            user_id=user_id,
            type="experience",
            title=f"Item {index}",
            end_date=date.today(),
        )
        bullets.append(BulletPoint(id=uuid4(), item_id=item.id, text=text, item=item))
    return jd, [requirement], bullets


def install_pipeline(
    monkeypatch,
    user_id,
    jd,
    requirements,
    bullets,
    dense_ids,
    sparse_ids,
    scores,
):
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, requirements, bullets)
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "vector_presence",
        lambda *_: ({str(bullet.id) for bullet in bullets}, {str(bullet.id) for bullet in bullets}),
    )
    monkeypatch.setattr(
        vector_store,
        "query_dense",
        Mock(return_value=[{"bullet_id": str(bullet_id)} for bullet_id in dense_ids]),
    )
    monkeypatch.setattr(
        vector_store,
        "query_sparse",
        Mock(return_value=[{"bullet_id": str(bullet_id)} for bullet_id in sparse_ids]),
    )

    def rerank(_query, candidates, _top_n):
        return [
            {**candidate, "score": scores[candidate["bullet_id"]]}
            for candidate in sorted(
                candidates, key=lambda item: scores[item["bullet_id"]], reverse=True
            )
        ]

    monkeypatch.setattr(vector_store, "rerank", Mock(side_effect=rerank))


async def test_unknown_technology_matches_only_real_mention(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = rows(
        user_id,
        "Apache Spark data processing",
        ["CGPA 7.7 with coursework in operating systems", "Built Apache Spark ETL pipelines"],
    )
    install_pipeline(
        monkeypatch,
        user_id,
        jd,
        requirements,
        bullets,
        dense_ids=[bullet.id for bullet in bullets],
        sparse_ids=[bullets[1].id],
        scores={str(bullets[0].id): 0.000019, str(bullets[1].id): 0.032101},
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert [match.id for match in result.requirements[0].matched_bullets] == [bullets[1].id]


async def test_conceptual_requirement_matches_dense_paraphrase(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = rows(
        user_id,
        "Cross-functional collaboration",
        ["Coordinated designers and engineers to deliver a company-wide launch"],
    )
    install_pipeline(
        monkeypatch,
        user_id,
        jd,
        requirements,
        bullets,
        dense_ids=[bullets[0].id],
        sparse_ids=[],
        scores={str(bullets[0].id): 0.005},
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.requirements[0].matched_bullets[0].id == bullets[0].id
    assert result.requirements[0].matched_bullets[0].confidence == "moderate"


async def test_dense_only_bullet_is_pending_and_not_matched(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = rows(user_id, "Python APIs", ["Built Python APIs"])
    install_pipeline(
        monkeypatch,
        user_id,
        jd,
        requirements,
        bullets,
        dense_ids=[bullets[0].id],
        sparse_ids=[],
        scores={str(bullets[0].id): 0.9},
    )
    monkeypatch.setattr(
        vector_store,
        "vector_presence",
        lambda *_: ({str(bullets[0].id)}, set()),
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.pending_embeddings is True
    assert result.requirements[0].no_match is True
    vector_store.rerank.assert_not_called()


async def test_rerank_score_threshold_and_confidence_bands(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = rows(
        user_id,
        "Python APIs",
        ["Built Python APIs", "Maintained internal services", "Painted signs"],
    )
    install_pipeline(
        monkeypatch,
        user_id,
        jd,
        requirements,
        bullets,
        dense_ids=[bullet.id for bullet in bullets],
        sparse_ids=[bullets[0].id],
        scores={
            str(bullets[0].id): 0.8,
            str(bullets[1].id): 0.005,
            str(bullets[2].id): 0.00001,
        },
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    confidences = {bullet.id: bullet.confidence for item in result.items for bullet in item.bullets}
    assert confidences == {bullets[0].id: "strong", bullets[1].id: "moderate"}


async def test_matching_foreign_jd_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(matcher, "async_session_factory", lambda: FakeSession(None, [], []))

    assert await matcher.match_jd(uuid4(), uuid4()) is None


async def test_reranker_failure_is_a_clear_api_error(monkeypatch) -> None:
    monkeypatch.setattr(
        matcher,
        "match_jd",
        AsyncMock(side_effect=vector_store.VectorStoreError("Pinecone reranker unavailable")),
    )

    with pytest.raises(HTTPException) as caught:
        await match_api.match_job_description(uuid4(), User(id=uuid4(), email="user@example.com"))

    assert caught.value.status_code == 502
    assert caught.value.detail == "Pinecone reranker unavailable"
