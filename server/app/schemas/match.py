from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


class MatchedRequirement(BaseModel):
    id: UUID
    text: str
    score: float
    confidence: Literal["strong", "moderate"]
    technology_evidence: list[str]


class MatchedBullet(BaseModel):
    bullet_point_id: UUID | None = None
    skill_bank_item_id: UUID | None = None
    text: str
    score: float
    confidence: Literal["strong", "moderate"]
    requirements: list[MatchedRequirement]

    @model_validator(mode="after")
    def exactly_one_source(self) -> "MatchedBullet":
        if (self.bullet_point_id is None) == (self.skill_bank_item_id is None):
            raise ValueError("exactly one match source ID is required")
        return self


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
    named_technologies: list[str]
    technology_match_mode: Literal["any", "all"] | None
    technology_evidence: list[str]
    no_match: bool


class MatchResult(BaseModel):
    jd_id: UUID
    pending_embeddings: bool
    requirements: list[RequirementMatch]
    items: list[MatchedItem]
