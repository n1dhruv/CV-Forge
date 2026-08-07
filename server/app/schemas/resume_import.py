from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ParsedResumeImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ResumeImportItem]
    skills: list[NonEmptyText]


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
    skills: list[NonEmptyText] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_selection(self) -> "ResumeImportCommit":
        if not self.items and not self.skills:
            raise ValueError("Select at least one item or skill")
        return self


class ResumeImportCommitResult(BaseModel):
    items: list[ItemDetail]
