from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class JDTextSubmission(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    raw_text: str = Field(min_length=1, max_length=100_000)


NonEmptyText = Annotated[str, Field(min_length=1)]


class JDTechnologyRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requirement: NonEmptyText
    named_technologies: list[NonEmptyText] = Field(min_length=1)
    match_mode: Literal["any", "all"]


class JDParsed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_skills: list[str]
    nice_to_have_skills: list[str]
    responsibilities: list[str]
    seniority: Literal["junior", "mid", "senior", "staff", "unspecified"]
    ats_keywords: list[str]
    action_verbs: list[str]
    technology_requirements: list[JDTechnologyRequirement]


class JDParseQueued(BaseModel):
    job_description_id: UUID
    background_job_id: UUID


class JDRequirementRead(BaseModel):
    id: UUID
    skill: str
    importance: Literal["required", "nice_to_have"]
    category: str | None
    named_technologies: list[str]
    technology_match_mode: Literal["any", "all"] | None


class JDDetail(BaseModel):
    id: UUID
    status: Literal["queued", "running", "done", "failed"]
    parsed_json: JDParsed | None
    requirements: list[JDRequirementRead]
    action_verbs: list[str]


class JDListItem(BaseModel):
    id: UUID
    excerpt: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime
