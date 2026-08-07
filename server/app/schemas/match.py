from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class MatchedRequirement(BaseModel):
    id: UUID
    text: str
    score: float
    confidence: Literal["strong", "moderate"]


class MatchedBullet(BaseModel):
    id: UUID
    text: str
    score: float
    confidence: Literal["strong", "moderate"]
    requirements: list[MatchedRequirement]


class MatchedItem(BaseModel):
    id: UUID
    type: str
    title: str
    org: str | None
    start_date: date | None
    end_date: date | None
    bullets: list[MatchedBullet]


class RequirementMatch(BaseModel):
    id: UUID
    text: str
    importance: Literal["required", "nice_to_have"]
    no_match: bool
    matched_bullets: list[MatchedBullet]


class MatchResult(BaseModel):
    jd_id: UUID
    pending_embeddings: bool
    requirements: list[RequirementMatch]
    items: list[MatchedItem]
