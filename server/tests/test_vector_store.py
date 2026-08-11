from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from app.api.skill_bank import routes
from app.models.skill_bank import BulletPoint, SkillBankItem
from app.models.user import User
from app.schemas.skill_bank import ItemCreate
from app.services import skill_bank, vector_store


class FakeIndex:
    def __init__(self) -> None:
        self.vectors: dict[str, dict[str, dict]] = {}

    def upsert(self, vectors, namespace):
        bucket = self.vectors.setdefault(namespace, {})
        for vector in vectors:
            bucket[vector["id"]] = vector

    def query(
        self,
        *,
        namespace,
        top_k,
        include_metadata,
        vector=None,
        sparse_vector=None,
    ):
        del include_metadata, vector, sparse_vector
        matches = [
            SimpleNamespace(id=record["id"], score=1.0, metadata=record["metadata"])
            for record in self.vectors.get(namespace, {}).values()
        ]
        return SimpleNamespace(matches=matches[:top_k])

    def fetch(self, *, ids, namespace):
        bucket = self.vectors.get(namespace, {})
        return SimpleNamespace(
            vectors={vector_id: bucket[vector_id] for vector_id in ids if vector_id in bucket}
        )

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


def indexes(monkeypatch):
    dense, sparse = FakeIndex(), FakeIndex()
    monkeypatch.setattr(vector_store, "_dense_index", lambda: dense)
    monkeypatch.setattr(vector_store, "_sparse_index", lambda: sparse)
    return dense, sparse


def store_both(user_id, bullet_id, item_id):
    metadata = {"item_id": str(item_id), "item_type": "experience"}
    vector_store.upsert_dense_vector(user_id, bullet_id, [1.0], metadata)
    vector_store.upsert_sparse_vector(
        user_id, bullet_id, {"indices": [1], "values": [1.0]}, metadata
    )


def store_item(user_id, item_id):
    metadata = {"item_id": str(item_id), "item_type": "skill"}
    vector_store.upsert_dense_vector(user_id, item_id, [1.0], metadata, "item")
    vector_store.upsert_sparse_vector(
        user_id, item_id, {"indices": [1], "values": [1.0]}, metadata, "item"
    )


def test_dense_and_sparse_queries_share_ids_and_namespace(monkeypatch) -> None:
    indexes(monkeypatch)
    user_id, bullet_id, item_id = uuid4(), uuid4(), uuid4()
    store_both(user_id, bullet_id, item_id)
    monkeypatch.setattr(
        vector_store,
        "sparse_embedding",
        lambda *_: {"indices": [1], "values": [1.0]},
    )

    assert vector_store.query_dense(user_id, [1.0], 1)[0]["bullet_id"] == str(bullet_id)
    assert vector_store.query_sparse(user_id, "Python", 1)[0]["bullet_id"] == str(bullet_id)
    assert vector_store.query_dense(user_id, [1.0], 1)[0]["level"] == "bullet"
    assert vector_store.vector_presence(user_id, [bullet_id]) == (
        {str(bullet_id)},
        {str(bullet_id)},
    )


async def test_delete_endpoint_removes_vector_from_both_indexes(monkeypatch) -> None:
    dense, sparse = indexes(monkeypatch)
    monkeypatch.setattr(
        skill_bank.asyncio,
        "to_thread",
        AsyncMock(side_effect=lambda function, *args: function(*args)),
    )
    user = User(id=uuid4(), email="a@example.com")
    bullet = BulletPoint(id=uuid4(), item_id=uuid4(), text="Built APIs")
    store_both(user.id, bullet.id, bullet.item_id)
    session = AsyncMock()
    session.scalar.return_value = bullet

    await routes.delete_bullet(bullet.id, session, user)

    assert dense.vectors[str(user.id)] == {}
    assert sparse.vectors[str(user.id)] == {}


async def test_delete_item_removes_vectors_from_both_indexes(monkeypatch) -> None:
    dense, sparse = indexes(monkeypatch)
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
        store_both(user.id, bullet_id, item.id)
    store_item(user.id, item.id)
    session = AsyncMock()
    session.scalar.return_value = item

    await routes.delete_skill_bank_item(item.id, session, user)

    assert dense.vectors[str(user.id)] == {}
    assert sparse.vectors[str(user.id)] == {}


def test_item_vectors_use_item_id_and_level_metadata(monkeypatch) -> None:
    dense, sparse = indexes(monkeypatch)
    user_id, item_id = uuid4(), uuid4()

    store_item(user_id, item_id)

    for index in (dense, sparse):
        record = index.vectors[str(user_id)][str(item_id)]
        assert record["metadata"]["level"] == "item"
        assert record["metadata"]["item_id"] == str(item_id)
        assert "bullet_id" not in record["metadata"]


async def test_creating_bulletless_item_queues_item_embedding(monkeypatch) -> None:
    user = User(id=uuid4(), email="a@example.com")
    item = SkillBankItem(id=uuid4(), user_id=user.id, type="skill", title="Kafka", bullet_points=[])
    session = AsyncMock()
    queue = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(arq=queue)))
    monkeypatch.setattr(routes.skill_bank, "create_item", AsyncMock(return_value=item))
    monkeypatch.setattr(routes.embeddings, "enqueue_items", AsyncMock())

    created = await routes.create_skill_bank_item(
        ItemCreate(type="skill", title="Kafka"), request, session, user
    )

    assert created is item
    routes.embeddings.enqueue_items.assert_awaited_once_with(session, queue, user.id, [item.id])


def test_ownership_isolation_holds_in_both_indexes(monkeypatch) -> None:
    indexes(monkeypatch)
    user_a, user_b = uuid4(), uuid4()
    bullet_a, bullet_b = uuid4(), uuid4()
    store_both(user_a, bullet_a, uuid4())
    store_both(user_b, bullet_b, uuid4())
    monkeypatch.setattr(
        vector_store,
        "sparse_embedding",
        lambda *_: {"indices": [1], "values": [1.0]},
    )

    dense_ids = {match["bullet_id"] for match in vector_store.query_dense(user_a, [1.0], 10)}
    sparse_ids = {match["bullet_id"] for match in vector_store.query_sparse(user_a, "API", 10)}

    assert dense_ids == {str(bullet_a)}
    assert sparse_ids == {str(bullet_a)}


def test_sparse_embedding_and_reranker_use_hosted_models(monkeypatch) -> None:
    inference = SimpleNamespace(
        embed=Mock(return_value=[{"sparse_indices": [4], "sparse_values": [0.75]}]),
    )
    monkeypatch.setattr(vector_store, "_client", lambda: SimpleNamespace(inference=inference))
    response = Mock()
    response.json.return_value = {"results": [{"index": 1, "relevance_score": 0.82}]}
    monkeypatch.setattr(vector_store.httpx, "post", Mock(return_value=response))
    candidates = [
        {"candidate_id": "bullet:a", "text": "Unrelated"},
        {"candidate_id": "bullet:b", "text": "Apache Spark pipelines"},
    ]

    sparse = vector_store.sparse_embedding("Apache Spark", "query")
    ranked = vector_store.rerank("Apache Spark", candidates, 1)

    assert sparse == {"indices": [4], "values": [0.75]}
    assert ranked == [{"candidate_id": "bullet:b", "text": "Apache Spark pipelines", "score": 0.82}]
    assert inference.embed.call_args.kwargs["parameters"]["input_type"] == "query"
    assert vector_store.httpx.post.call_args.kwargs["json"]["model"] == (
        "nvidia/llama-nemotron-rerank-vl-1b-v2:free"
    )
    assert vector_store.httpx.post.call_args.kwargs["json"]["documents"] == [
        "Unrelated",
        "Apache Spark pipelines",
    ]
