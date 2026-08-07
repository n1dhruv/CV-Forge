from datetime import date
from unittest.mock import AsyncMock
from uuid import uuid4

from app.models.resume import JDRequirement, JobDescription
from app.models.skill_bank import BulletPoint, SkillBankItem
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


def fixture_rows(user_id):
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Python APIs", status="done")
    requirement = JDRequirement(
        id=uuid4(), jd_id=jd.id, skill="Build Python APIs", importance="required"
    )
    relevant_item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="experience", title="Backend", end_date=date.today()
    )
    unrelated_item = SkillBankItem(id=uuid4(), user_id=user_id, type="project", title="Design")
    relevant = BulletPoint(
        id=uuid4(), item_id=relevant_item.id, text="Built Python APIs", item=relevant_item
    )
    unrelated = BulletPoint(
        id=uuid4(), item_id=unrelated_item.id, text="Painted landscape posters", item=unrelated_item
    )
    return jd, [requirement], [relevant, unrelated]


async def test_matching_ranks_semantic_and_keyword_overlap(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = fixture_rows(user_id)
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, requirements, bullets)
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [
            {"bullet_id": str(bullets[0].id), "score": 0.95, "metadata": {}},
            {"bullet_id": str(bullets[1].id), "score": 0.1, "metadata": {}},
        ],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.items[0].bullets[0].id == bullets[0].id
    assert result.pending_embeddings is False


async def test_matching_reports_pending_embeddings(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = fixture_rows(user_id)
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, requirements, bullets)
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [{"bullet_id": str(uuid4()), "score": 1.0, "metadata": {}}],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.pending_embeddings is True
    assert result.items == []


async def test_matching_foreign_jd_returns_none(monkeypatch) -> None:
    monkeypatch.setattr(matcher, "async_session_factory", lambda: FakeSession(None, [], []))

    assert await matcher.match_jd(uuid4(), uuid4()) is None


async def test_named_technology_rejects_closest_unrelated_candidate(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Kafka", status="done")
    requirement = JDRequirement(
        id=uuid4(),
        jd_id=jd.id,
        skill="Event-driven systems using Kafka, RabbitMQ, or SQS",
        importance="required",
    )
    item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="education", title="B.Tech", end_date=date.today()
    )
    bullet = BulletPoint(
        id=uuid4(),
        item_id=item.id,
        text="CGPA 7.7; coursework in Data Structures, DBMS, OS, and Networks",
        item=item,
    )
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [bullet])
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [{"bullet_id": str(bullet.id), "score": 0.99, "metadata": {}}],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.items == []
    assert result.requirements[0].no_match is True
    assert result.requirements[0].matched_bullets == []


async def test_named_technology_matches_real_mention(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Kafka", status="done")
    requirement = JDRequirement(
        id=uuid4(), jd_id=jd.id, skill="Kafka event streaming", importance="required"
    )
    item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="experience", title="Platform", end_date=date.today()
    )
    bullet = BulletPoint(
        id=uuid4(), item_id=item.id, text="Built event streaming with Apache Kafka", item=item
    )
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [bullet])
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [{"bullet_id": str(bullet.id), "score": 0.70, "metadata": {}}],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.requirements[0].no_match is False
    assert result.requirements[0].matched_bullets[0].id == bullet.id


async def test_conceptual_requirement_still_matches_a_paraphrase(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Leadership", status="done")
    requirement = JDRequirement(
        id=uuid4(),
        jd_id=jd.id,
        skill="Led cross-functional projects",
        importance="required",
    )
    item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="experience", title="Lead", end_date=date.today()
    )
    bullet = BulletPoint(
        id=uuid4(),
        item_id=item.id,
        text="Coordinated designers and engineers to deliver a company-wide launch",
        item=item,
    )
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, [requirement], [bullet])
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [{"bullet_id": str(bullet.id), "score": 0.80, "metadata": {}}],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.requirements[0].matched_bullets[0].id == bullet.id


async def test_api_confidence_uses_fixed_score_bands(monkeypatch) -> None:
    user_id = uuid4()
    jd = JobDescription(id=uuid4(), user_id=user_id, raw_text="Leadership", status="done")
    requirement = JDRequirement(
        id=uuid4(), jd_id=jd.id, skill="Led cross-functional projects", importance="required"
    )
    strong_item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="experience", title="Strong", end_date=date.today()
    )
    moderate_item = SkillBankItem(
        id=uuid4(), user_id=user_id, type="project", title="Moderate", end_date=date.today()
    )
    strong = BulletPoint(
        id=uuid4(), item_id=strong_item.id, text="Led cross-functional projects", item=strong_item
    )
    moderate = BulletPoint(
        id=uuid4(),
        item_id=moderate_item.id,
        text="Coordinated specialists to deliver a shared initiative",
        item=moderate_item,
    )
    monkeypatch.setattr(
        matcher,
        "async_session_factory",
        lambda: FakeSession(jd, [requirement], [strong, moderate]),
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [
            {"bullet_id": str(strong.id), "score": 0.90, "metadata": {}},
            {"bullet_id": str(moderate.id), "score": 0.60, "metadata": {}},
        ],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    confidences = {bullet.id: bullet.confidence for item in result.items for bullet in item.bullets}
    assert confidences == {strong.id: "strong", moderate.id: "moderate"}


async def test_requirement_with_no_qualifying_candidates_is_explicit(monkeypatch) -> None:
    user_id = uuid4()
    jd, requirements, bullets = fixture_rows(user_id)
    monkeypatch.setattr(
        matcher, "async_session_factory", lambda: FakeSession(jd, requirements, bullets)
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        matcher.asyncio, "to_thread", AsyncMock(side_effect=lambda function, *args: function(*args))
    )
    monkeypatch.setattr(
        vector_store,
        "query_similar",
        lambda *args: [
            {"bullet_id": str(bullets[0].id), "score": -0.20, "metadata": {}},
            {"bullet_id": str(bullets[1].id), "score": -0.30, "metadata": {}},
        ],
    )

    result = await matcher.match_jd(user_id, jd.id)

    assert result is not None
    assert result.requirements[0].no_match is True
    assert result.requirements[0].matched_bullets == []
