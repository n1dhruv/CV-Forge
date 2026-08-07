from datetime import date
from uuid import UUID

from pydantic import BaseModel


class MatchedRequirement(BaseModel):
    id: UUID
    text: str
    score: float


class MatchedBullet(BaseModel):
    id: UUID
    text: str
    score: float
    requirements: list[MatchedRequirement]


class MatchedItem(BaseModel):
    id: UUID
    type: str
    title: str
    org: str | None
    start_date: date | None
    end_date: date | None
    bullets: list[MatchedBullet]


class MatchResult(BaseModel):
    jd_id: UUID
    pending_embeddings: bool
    items: list[MatchedItem]
