from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.profile import ProfileImport
from app.schemas.skill_bank import ItemDetail

ImportItemType = Literal["experience", "project", "education", "certification"]
NonEmptyText = Annotated[str, Field(min_length=1)]


class ResumeImportItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    type: ImportItemType
    title: str = Field(min_length=1)
    org: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    bullets: list[NonEmptyText]


class ResumeImportSkill(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    category: str | None = Field(default=None, max_length=80)

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value


def _normalize_skills(value: object) -> object:
    if isinstance(value, list):
        return [{"name": skill} if isinstance(skill, str) else skill for skill in value]
    return value


class ParsedResumeImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResumeImportItem]
    skills: list[ResumeImportSkill]
    profile: ProfileImport | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_legacy_skills(cls, value: object) -> object:
        return _normalize_skills(value)


class ResumeImportQueued(BaseModel):
    resume_import_id: UUID
    background_job_id: UUID


class ResumeImportDetail(BaseModel):
    id: UUID
    status: Literal["queued", "running", "done", "failed"]
    parsed_json: ParsedResumeImport | None
    created_at: datetime
    committed_at: datetime | None


class ResumeImportListItem(BaseModel):
    id: UUID
    excerpt: str
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime


class ResumeImportCommit(BaseModel):
    items: list[ResumeImportItem] = Field(default_factory=list)
    skills: list[ResumeImportSkill] = Field(default_factory=list)
    profile: ProfileImport | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_legacy_skills(cls, value: object) -> object:
        return _normalize_skills(value)

    @model_validator(mode="after")
    def require_selection(self) -> "ResumeImportCommit":
        if not self.items and not self.skills and not (self.profile and self.profile.non_empty_values()):
            raise ValueError("Select at least one item or skill")
        return self


class ResumeImportCommitResult(BaseModel):
    items: list[ItemDetail]
