from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.api.skill_bank import routes
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.services import skill_bank, vector_store


class FakeIndex:
    def __init__(self) -> None:
        self.vectors: dict[str, dict[str, dict]] = {}

    def upsert(self, vectors, namespace):
        bucket = self.vectors.setdefault(namespace, {})
        for vector in vectors:
            bucket[vector["id"]] = vector

    def query(self, namespace, vector, top_k, filter, include_metadata):
        del vector, include_metadata
        matches = []
        for record in self.vectors.get(namespace, {}).values():
            if filter and any(
                record["metadata"].get(key) != condition["$eq"] for key, condition in filter.items()
            ):
                continue
            matches.append(SimpleNamespace(id=record["id"], score=1.0, metadata=record["metadata"]))
        return SimpleNamespace(matches=matches[:top_k])

    def delete(self, *, namespace, ids=None, filter=None):
        bucket = self.vectors.setdefault(namespace, {})
        if ids:
            for vector_id in ids:
                bucket.pop(vector_id, None)
        if filter:
            for vector_id, record in list(bucket.items()):
                if all(
                    record["metadata"].get(key) == condition["$eq"]
                    for key, condition in filter.items()
                ):
                    del bucket[vector_id]


def test_upsert_and_query_returns_bullet_in_user_namespace(monkeypatch) -> None:
    index = FakeIndex()
    monkeypatch.setattr(vector_store, "_index", lambda: index)
    user_id, bullet_id, item_id = uuid4(), uuid4(), uuid4()

    vector_store.upsert_vector(
        user_id,
        bullet_id,
        [1.0, 0.0],
        {"item_id": str(item_id), "item_type": "experience"},
    )

    assert vector_store.query_similar(user_id, [1.0, 0.0], 1)[0]["bullet_id"] == str(bullet_id)


async def test_delete_endpoint_removes_vector_from_index(monkeypatch) -> None:
    index = FakeIndex()
    monkeypatch.setattr(vector_store, "_index", lambda: index)
    monkeypatch.setattr(
        skill_bank.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda function, *args: function(*args)),
    )
    user = User(id=uuid4(), email="a@example.com")
    bullet = BulletPoint(id=uuid4(), item_id=uuid4(), text="Built APIs")
    vector_store.upsert_vector(
        user.id,
        bullet.id,
        [1.0],
        {"item_id": str(bullet.item_id), "item_type": "experience"},
    )
    session = AsyncMock()
    session.scalar.return_value = bullet

    await routes.delete_bullet(bullet.id, session, user)

    assert index.vectors[str(user.id)] == {}


async def test_delete_item_endpoint_bulk_removes_its_vectors(monkeypatch) -> None:
    index = FakeIndex()
    monkeypatch.setattr(vector_store, "_index", lambda: index)
    monkeypatch.setattr(
        skill_bank.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda function, *args: function(*args)),
    )
    user = User(id=uuid4(), email="a@example.com")
    item = SkillBankItem(
        id=uuid4(), user_id=user.id, type="experience", title="Backend", bullet_points=[]
    )
    for bullet_id in (uuid4(), uuid4()):
        vector_store.upsert_vector(
            user.id,
            bullet_id,
            [1.0],
            {"item_id": str(item.id), "item_type": item.type},
        )
    session = AsyncMock()
    session.scalar.return_value = item

    await routes.delete_skill_bank_item(item.id, session, user)

    assert index.vectors[str(user.id)] == {}


def test_crafted_user_filter_cannot_cross_namespace(monkeypatch) -> None:
    index = FakeIndex()
    monkeypatch.setattr(vector_store, "_index", lambda: index)
    user_a, user_b = uuid4(), uuid4()
    vector_store.upsert_vector(
        user_a, uuid4(), [1.0], {"item_id": str(uuid4()), "item_type": "project"}
    )
    vector_store.upsert_vector(
        user_b, uuid4(), [1.0], {"item_id": str(uuid4()), "item_type": "project"}
    )

    results = vector_store.query_similar(user_a, [1.0], 10, {"user_id": {"$eq": str(user_b)}})

    assert results == []
