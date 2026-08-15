import asyncio
from datetime import date
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import match as match_api
from app.models.jobs import BackgroundJob
from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.match import MatchResult, MatchedBullet, MatchedItem, MatchedRequirement
from app.services import llm_client, matcher, vector_store
from app.workers import match as match_worker


class Result:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class FakeSession:
    def __init__(self, description, requirements, items):
        self.description = description
        self.results = iter([requirements, items])

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
    items = list({bullet.item.id: bullet.item for bullet in bullets}.values())
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, requirements, items)
    )
    monkeypatch.setattr(
        llm_client,
        "get_embeddings",
        AsyncMock(return_value=[[1.0] for _ in requirements]),
    )
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "vector_presence",
        lambda *_: (
            {
                str(record_id)
                for record_id in [*(bullet.id for bullet in bullets), *(item.id for item in items)]
            },
            {
                str(record_id)
                for record_id in [*(bullet.id for bullet in bullets), *(item.id for item in items)]
            },
        ),
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
            {**candidate, "score": scores[candidate["record_id"]]}
            for candidate in sorted(
                candidates, key=lambda item: scores[item["record_id"]], reverse=True
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
    assert [match.bullet_point_id for item in result.items for match in item.bullets] == [
        bullets[1].id
    ]
    assert "matched_bullets" not in result.requirements[0].model_dump()


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
    assert result.items[0].bullets[0].bullet_point_id == bullets[0].id
    assert result.items[0].bullets[0].confidence == "moderate"


async def test_matcher_batches_requirement_embeddings(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = rows(user_id, "Python APIs", ["Built Python APIs"])
    requirements.append(
        JDRequirement(
            id=uuid4(),
            jd_id=jd.id,
            skill="Apache Kafka",
            importance="nice_to_have",
        )
    )
    install_pipeline(
        monkeypatch,
        user_id,
        jd,
        requirements,
        bullets,
        dense_ids=[bullets[0].id],
        sparse_ids=[bullets[0].id],
        scores={str(bullets[0].id): 0.8},
    )

    await matcher.match_jd(user_id, jd.id)

    llm_client.get_embeddings.assert_awaited_once_with(user_id, ["Python APIs", "Apache Kafka"])


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
    confidences = {
        bullet.bullet_point_id: bullet.confidence
        for item in result.items
        for bullet in item.bullets
    }
    assert confidences == {bullets[0].id: "strong", bullets[1].id: "moderate"}
    recommended = {
        bullet.bullet_point_id: bullet.recommended
        for item in result.items
        for bullet in item.bullets
    }
    assert recommended == {bullets[0].id: True, bullets[1].id: False}


def test_recommendations_prioritize_required_matches_and_cap_experience_items() -> None:
    def item(score: float, importance: str) -> MatchedItem:
        bullet = MatchedBullet(
            bullet_point_id=uuid4(),
            text="Evidence",
            score=score,
            confidence="strong",
            requirements=[
                MatchedRequirement(
                    id=uuid4(), text="Requirement", importance=importance, score=score,
                    confidence="strong", technology_evidence=[]
                )
            ],
        )
        return MatchedItem(id=uuid4(), type="experience", title="Role", org=None, start_date=None, end_date=None, bullets=[bullet])

    required_low, required_high, nice_high = item(0.7, "required"), item(0.8, "required"), item(0.99, "nice_to_have")
    matcher._recommend([nice_high, required_low, required_high])

    assert [row.bullets[0].recommended for row in (required_low, required_high, nice_high)] == [
        True,
        True,
        False,
    ]


async def test_matching_foreign_jd_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(matcher, "async_session_factory", lambda: FakeSession(None, [], []))

    assert await matcher.match_jd(uuid4(), uuid4()) is None


async def test_bulletless_kafka_skill_matches_requirement(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Kafka", status="done")
    requirement = JDRequirement(id=uuid4(), jd_id=jd.id, skill="Kafka", importance="required")
    item = SkillBankItem(id=uuid4(), user_id=user_id, type="skill", title="Kafka", bullet_points=[])
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [item])
    )
    monkeypatch.setattr(llm_client, "get_embeddings", AsyncMock(return_value=[[1.0]]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "vector_presence",
        lambda *_: ({str(item.id)}, {str(item.id)}),
    )
    item_match = {"level": "item", "item_id": str(item.id)}
    monkeypatch.setattr(vector_store, "query_dense", Mock(return_value=[item_match]))
    monkeypatch.setattr(vector_store, "query_sparse", Mock(return_value=[item_match]))
    monkeypatch.setattr(
        vector_store,
        "rerank",
        Mock(side_effect=lambda _query, candidates, _top_n: [{**candidates[0], "score": 0.9}]),
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    match = result.items[0].bullets[0]
    assert match.skill_bank_item_id == item.id
    assert match.bullet_point_id is None
    assert match.text == "Kafka"
    assert result.pending_embeddings is False


async def test_unembedded_bulletless_skill_sets_pending(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Kafka", status="done")
    requirement = JDRequirement(id=uuid4(), jd_id=jd.id, skill="Kafka", importance="required")
    item = SkillBankItem(id=uuid4(), user_id=user_id, type="skill", title="Kafka", bullet_points=[])
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [item])
    )
    monkeypatch.setattr(llm_client, "get_embeddings", AsyncMock(return_value=[[1.0]]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(vector_store, "vector_presence", lambda *_: (set(), set()))
    monkeypatch.setattr(vector_store, "query_dense", Mock(return_value=[]))
    monkeypatch.setattr(vector_store, "query_sparse", Mock(return_value=[]))
    monkeypatch.setattr(vector_store, "rerank", Mock())

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.pending_embeddings is True
    assert result.requirements[0].no_match is True


async def test_item_and_child_bullet_are_deduplicated_per_requirement(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Kafka", status="done")
    requirement = JDRequirement(id=uuid4(), jd_id=jd.id, skill="Kafka", importance="required")
    item = SkillBankItem(id=uuid4(), user_id=user_id, type="skill", title="Kafka")
    bullet = BulletPoint(id=uuid4(), item_id=item.id, text="Operated Kafka clusters", item=item)
    item.bullet_points = [bullet]
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [item])
    )
    monkeypatch.setattr(llm_client, "get_embeddings", AsyncMock(return_value=[[1.0]]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    present = {str(item.id), str(bullet.id)}
    monkeypatch.setattr(vector_store, "vector_presence", lambda *_: (present, present))
    matches = [
        {"level": "item", "item_id": str(item.id)},
        {"level": "bullet", "bullet_id": str(bullet.id)},
    ]
    monkeypatch.setattr(vector_store, "query_dense", Mock(return_value=matches))
    monkeypatch.setattr(vector_store, "query_sparse", Mock(return_value=[]))

    def rerank(_query, candidates, _top_n):
        scores = {"item": 0.8, "bullet": 0.9}
        return [{**candidate, "score": scores[candidate["level"]]} for candidate in candidates]

    monkeypatch.setattr(vector_store, "rerank", Mock(side_effect=rerank))

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert len(result.items[0].bullets) == 1
    assert result.items[0].bullets[0].bullet_point_id == bullet.id
    assert result.items[0].bullets[0].skill_bank_item_id is None


def test_match_evidence_requires_exactly_one_source_id() -> None:
    values = {
        "text": "Kafka",
        "score": 0.9,
        "confidence": "strong",
        "requirements": [],
    }
    with pytest.raises(ValidationError):
        MatchedBullet(**values)
    with pytest.raises(ValidationError):
        MatchedBullet(
            **values,
            bullet_point_id=uuid4(),
            skill_bank_item_id=uuid4(),
        )


async def test_match_api_returns_matcher_result(monkeypatch) -> None:
    user = User(id=uuid4(), email="user@example.com")
    jd_id = uuid4()
    match = MatchResult(jd_id=jd_id, pending_embeddings=False, requirements=[], items=[])
    monkeypatch.setattr(matcher, "match_jd", AsyncMock(return_value=match))

    result = await match_api.match_job_description(jd_id, user)

    assert result is match
    matcher.match_jd.assert_awaited_once_with(user.id, jd_id)


async def test_match_api_returns_vector_failure(monkeypatch) -> None:
    user = User(id=uuid4(), email="user@example.com")
    monkeypatch.setattr(
        matcher,
        "match_jd",
        AsyncMock(
            side_effect=vector_store.VectorStoreError(
                "OpenRouter reranker unavailable (429)"
            )
        ),
    )

    with pytest.raises(HTTPException) as caught:
        await match_api.match_job_description(uuid4(), user)

    assert caught.value.status_code == 502
    assert caught.value.detail == "OpenRouter reranker unavailable (429)"


async def test_match_worker_persists_success(monkeypatch) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    result = MatchResult(
        jd_id=jd_id,
        pending_embeddings=False,
        requirements=[],
        items=[],
    )
    finish = AsyncMock()
    monkeypatch.setattr(match_worker, "_finish", finish)
    monkeypatch.setattr(matcher, "match_jd", AsyncMock(return_value=result))

    await match_worker.match_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert finish.await_count == 2
    assert finish.await_args_list[-1].args == (job_id, user_id, "done")
    assert finish.await_args_list[-1].kwargs["result"] == result.model_dump(mode="json")


async def test_match_worker_persists_provider_failure(monkeypatch) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    finish = AsyncMock()
    monkeypatch.setattr(match_worker, "_finish", finish)
    monkeypatch.setattr(
        matcher,
        "match_jd",
        AsyncMock(side_effect=vector_store.VectorStoreError("Pinecone reranker unavailable")),
    )

    await match_worker.match_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert finish.await_args_list[-1].args == (job_id, user_id, "failed")
    assert finish.await_args_list[-1].kwargs["error"] == "Pinecone reranker unavailable"


async def test_match_worker_persists_timeout(monkeypatch) -> None:
    user_id, jd_id, job_id = uuid4(), uuid4(), uuid4()
    finish = AsyncMock()
    monkeypatch.setattr(match_worker, "_finish", finish)
    monkeypatch.setattr(
        matcher,
        "match_jd",
        AsyncMock(side_effect=asyncio.CancelledError),
    )

    with pytest.raises(asyncio.CancelledError):
        await match_worker.match_jd_task({}, str(jd_id), str(job_id), str(user_id))

    assert finish.await_args_list[-1].args == (job_id, user_id, "failed")
    assert finish.await_args_list[-1].kwargs["error"] == "Matching timed out — try again"


async def test_match_worker_finish_updates_background_job(monkeypatch) -> None:
    user_id, job_id = uuid4(), uuid4()
    job = BackgroundJob(id=job_id, user_id=user_id, job_type="match", status="running")
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.scalar.return_value = job
    monkeypatch.setattr(match_worker, "async_session_factory", lambda: session)
    result = {"jd_id": str(uuid4()), "requirements": [], "items": []}

    await match_worker._finish(job_id, user_id, "done", result=result)

    assert job.status == "done"
    assert job.result == result
    assert job.error is None
    session.commit.assert_awaited_once()
