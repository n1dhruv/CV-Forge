from functools import lru_cache
from typing import Any
from uuid import UUID

from pinecone import Pinecone

from app.core.config import get_settings


@lru_cache
def _index() -> Any:
    settings = get_settings()
    client = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
    return client.Index(name=settings.pinecone_index_name, host=settings.pinecone_host)


def upsert_vector(user_id: UUID, bullet_id: UUID, embedding: list[float], metadata: dict) -> None:
    stored_metadata = {
        **metadata,
        "user_id": str(user_id),
        "bullet_id": str(bullet_id),
        "item_id": str(metadata["item_id"]),
        "item_type": str(metadata["item_type"]),
    }
    _index().upsert(
        vectors=[{"id": str(bullet_id), "values": embedding, "metadata": stored_metadata}],
        namespace=str(user_id),
    )


def query_similar(
    user_id: UUID,
    embedding: list[float],
    top_k: int,
    metadata_filter: dict | None = None,
) -> list[dict]:
    response = _index().query(
        namespace=str(user_id),
        vector=embedding,
        top_k=top_k,
        filter=metadata_filter,
        include_metadata=True,
    )
    matches = response.matches if hasattr(response, "matches") else response.get("matches", [])
    return [
        {
            "bullet_id": match.id if hasattr(match, "id") else match["id"],
            "score": float(match.score if hasattr(match, "score") else match["score"]),
            "metadata": (
                match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
            ),
        }
        for match in matches
    ]


def delete_vector(user_id: UUID, bullet_id: UUID) -> None:
    _index().delete(ids=[str(bullet_id)], namespace=str(user_id))


def delete_vectors_for_item(user_id: UUID, item_id: UUID) -> None:
    _index().delete(
        filter={"item_id": {"$eq": str(item_id)}},
        namespace=str(user_id),
    )
