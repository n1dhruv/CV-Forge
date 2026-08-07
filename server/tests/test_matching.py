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
