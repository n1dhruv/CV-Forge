from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.models.jobs import BackgroundJob
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.services import llm_client, vector_store
from app.workers import embeddings


class FakeSession:
    def __init__(self, bullet, job):
        self.bullet = bullet
        self.job = job
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def scalar(self, statement):
        del statement
        self.calls += 1
        return self.bullet if self.calls == 1 else self.job

    async def commit(self):
        return None


async def test_sparse_success_is_recorded_when_dense_embedding_fails(monkeypatch) -> None:
    user_id, bullet_id, job_id = uuid4(), uuid4(), uuid4()
    item = SkillBankItem(id=uuid4(), user_id=user_id, type="experience", title="Backend")
    bullet = BulletPoint(id=bullet_id, item_id=item.id, text="Built APIs", item=item)
    job = BackgroundJob(id=job_id, user_id=user_id, job_type="embedding", status="queued")
    session = FakeSession(bullet, job)
    monkeypatch.setattr(embeddings, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        embeddings.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda function, *args: function(*args)),
    )
    monkeypatch.setattr(
        llm_client,
        "get_embedding",
        AsyncMock(side_effect=llm_client.LLMNotConfiguredError()),
    )
    monkeypatch.setattr(
        vector_store,
        "sparse_embedding",
        Mock(return_value={"indices": [1], "values": [1.0]}),
    )
    monkeypatch.setattr(vector_store, "upsert_dense_vector", Mock())
    monkeypatch.setattr(vector_store, "upsert_sparse_vector", Mock())

    await embeddings.embed_bullet_task({}, str(bullet_id), str(job_id), str(user_id))

    assert job.status == "failed"
    assert job.result == {
        "bullet_id": str(bullet_id),
        "dense_stored": False,
        "sparse_stored": True,
    }
    assert job.error == "No embedding provider configured"
    vector_store.upsert_dense_vector.assert_not_called()
    vector_store.upsert_sparse_vector.assert_called_once()


async def test_bulletless_skill_item_gets_item_level_vectors(monkeypatch) -> None:
    user_id, item_id, job_id = uuid4(), uuid4(), uuid4()
    item = SkillBankItem(
        id=item_id,
        user_id=user_id,
        type="skill",
        title="Kafka",
        tags=["streaming"],
        raw_text="Built event-driven services",
        bullet_points=[],
    )
    job = BackgroundJob(id=job_id, user_id=user_id, job_type="embedding", status="queued")
    session = FakeSession(item, job)
    monkeypatch.setattr(embeddings, "async_session_factory", lambda: session)
    monkeypatch.setattr(
        embeddings.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda function, *args: function(*args)),
    )
    monkeypatch.setattr(llm_client, "get_embedding", AsyncMock(return_value=[1.0]))
    monkeypatch.setattr(
        vector_store,
        "sparse_embedding",
        Mock(return_value={"indices": [1], "values": [1.0]}),
    )
    monkeypatch.setattr(vector_store, "upsert_dense_vector", Mock())
    monkeypatch.setattr(vector_store, "upsert_sparse_vector", Mock())

    await embeddings.embed_item_task({}, str(item_id), str(job_id), str(user_id))

    assert job.status == "done"
    assert job.result == {
        "item_id": str(item_id),
        "dense_stored": True,
        "sparse_stored": True,
    }
    assert llm_client.get_embedding.await_args.args[1] == (
        "Kafka\nTags: streaming\nBuilt event-driven services"
    )
    assert vector_store.upsert_dense_vector.call_args.args[-1] == "item"
    assert vector_store.upsert_sparse_vector.call_args.args[-1] == "item"
