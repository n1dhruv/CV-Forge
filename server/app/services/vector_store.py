from functools import lru_cache
from typing import Any, Literal
from uuid import UUID

import httpx
from pinecone import Pinecone

from app.core.config import get_settings

SPARSE_MODEL = "pinecone-sparse-english-v0"
OPENROUTER_RERANK_URL = "https://openrouter.ai/api/v1/rerank"
FETCH_BATCH_SIZE = 1000


class VectorStoreError(Exception):
    pass


@lru_cache
def _client() -> Pinecone:
    return Pinecone(api_key=get_settings().pinecone_api_key.get_secret_value())


@lru_cache
def _dense_index() -> Any:
    settings = get_settings()
    return _client().Index(name=settings.pinecone_index_name, host=settings.pinecone_host)


@lru_cache
def _sparse_index() -> Any:
    return _client().Index(name=get_settings().pinecone_sparse_index_name)


def _metadata(user_id: UUID, record_id: UUID, metadata: dict, level: str) -> dict:
    result = {
        **metadata,
        "user_id": str(user_id),
        "item_id": str(metadata["item_id"]),
        "level": level,
        "item_type": str(metadata["item_type"]),
    }
    if level == "bullet":
        result["bullet_id"] = str(record_id)
    return result


def sparse_embedding(text: str, input_type: Literal["passage", "query"]) -> dict:
    try:
        embedding = _client().inference.embed(
            model=SPARSE_MODEL,
            inputs=[text],
            parameters={"input_type": input_type, "truncate": "END"},
        )[0]
        return {
            "indices": list(embedding["sparse_indices"]),
            "values": [float(value) for value in embedding["sparse_values"]],
        }
    except Exception as exc:
        raise VectorStoreError("Pinecone sparse embedding unavailable") from exc


def upsert_dense_vector(
    user_id: UUID,
    record_id: UUID,
    embedding: list[float],
    metadata: dict,
    level: Literal["bullet", "item"] = "bullet",
) -> None:
    try:
        _dense_index().upsert(
            vectors=[
                {
                    "id": str(record_id),
                    "values": embedding,
                    "metadata": _metadata(user_id, record_id, metadata, level),
                }
            ],
            namespace=str(user_id),
        )
    except Exception as exc:
        raise VectorStoreError("Pinecone could not store the dense embedding") from exc


def upsert_sparse_vector(
    user_id: UUID,
    record_id: UUID,
    sparse_values: dict,
    metadata: dict,
    level: Literal["bullet", "item"] = "bullet",
) -> None:
    try:
        _sparse_index().upsert(
            vectors=[
                {
                    "id": str(record_id),
                    "sparse_values": sparse_values,
                    "metadata": _metadata(user_id, record_id, metadata, level),
                }
            ],
            namespace=str(user_id),
        )
    except Exception as exc:
        raise VectorStoreError("Pinecone could not store the sparse embedding") from exc


def _matches(response: Any) -> list[dict]:
    matches = response.matches if hasattr(response, "matches") else response.get("matches", [])
    results = []
    for match in matches:
        record_id = match.id if hasattr(match, "id") else match["id"]
        metadata = match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
        level = metadata.get("level", "bullet")
        results.append(
            {
                "id": record_id,
                "level": level,
                "bullet_id": record_id if level == "bullet" else None,
                "item_id": metadata.get("item_id") if level == "item" else None,
                "score": float(match.score if hasattr(match, "score") else match["score"]),
                "metadata": metadata,
            }
        )
    return results


def query_dense(user_id: UUID, embedding: list[float], top_k: int) -> list[dict]:
    try:
        return _matches(
            _dense_index().query(
                namespace=str(user_id),
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
            )
        )
    except Exception as exc:
        raise VectorStoreError("Pinecone dense search unavailable") from exc


def query_sparse(user_id: UUID, query_text: str, top_k: int) -> list[dict]:
    embedding = sparse_embedding(query_text, "query")
    try:
        return _matches(
            _sparse_index().query(
                namespace=str(user_id),
                sparse_vector=embedding,
                top_k=top_k,
                include_metadata=True,
            )
        )
    except Exception as exc:
        raise VectorStoreError("Pinecone sparse search unavailable") from exc


def rerank(query_text: str, candidates: list[dict], top_n: int) -> list[dict]:
    if not candidates:
        return []
    try:
        settings = get_settings()
        response = httpx.post(
            OPENROUTER_RERANK_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"
            },
            json={
                "model": settings.openrouter_rerank_model,
                "query": query_text,
                "documents": [candidate["text"] for candidate in candidates],
                "top_n": min(top_n, len(candidates)),
            },
            timeout=30,
        )
        response.raise_for_status()
        return [
            {
                **candidates[int(item["index"])],
                "score": float(item["relevance_score"]),
            }
            for item in response.json()["results"]
        ]
    except httpx.HTTPStatusError as exc:
        raise VectorStoreError(
            f"OpenRouter reranker unavailable ({exc.response.status_code})"
        ) from exc
    except Exception as exc:
        raise VectorStoreError("OpenRouter reranker unavailable") from exc


def _fetched_ids(index: Any, namespace: str, record_ids: list[str]) -> set[str]:
    present: set[str] = set()
    for start in range(0, len(record_ids), FETCH_BATCH_SIZE):
        response = index.fetch(
            ids=record_ids[start : start + FETCH_BATCH_SIZE], namespace=namespace
        )
        vectors = response.vectors if hasattr(response, "vectors") else response.get("vectors", {})
        present.update(str(vector_id) for vector_id in vectors)
    return present


def vector_presence(user_id: UUID, record_ids: list[UUID]) -> tuple[set[str], set[str]]:
    ids = [str(record_id) for record_id in record_ids]
    try:
        return (
            _fetched_ids(_dense_index(), str(user_id), ids),
            _fetched_ids(_sparse_index(), str(user_id), ids),
        )
    except Exception as exc:
        raise VectorStoreError("Pinecone vector readiness check unavailable") from exc


def delete_vectors(user_id: UUID, bullet_id: UUID) -> None:
    try:
        for index in (_dense_index(), _sparse_index()):
            index.delete(ids=[str(bullet_id)], namespace=str(user_id))
    except Exception as exc:
        raise VectorStoreError("Pinecone could not delete this bullet's vectors") from exc


def delete_vectors_for_item(user_id: UUID, item_id: UUID) -> None:
    try:
        for index in (_dense_index(), _sparse_index()):
            index.delete(ids=[str(item_id)], namespace=str(user_id))
            index.delete(
                filter={"item_id": {"$eq": str(item_id)}},
                namespace=str(user_id),
            )
    except Exception as exc:
        raise VectorStoreError("Pinecone could not delete this item's vectors") from exc
