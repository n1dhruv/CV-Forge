from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResumeVersionCreate(BaseModel):
    jd_id: UUID


ResumeVersionStatus = Literal[
    "draft",
    "rewriting",
    "reviewing",
    "finalized",
    "assembling",
    "assembled",
    "compiling",
    "compiled",
    "compile_failed",
]


class ResumeVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    jd_id: UUID | None
    status: ResumeVersionStatus
    name: str
    version_label: str


class ResumeMetadataUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    version_label: str | None = Field(default=None, max_length=80)

    @field_validator("name", "version_label")
    @classmethod
    def trim_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value cannot be empty")
        return value

    @model_validator(mode="after")
    def has_change(self) -> Self:
        if self.name is None and self.version_label is None:
            raise ValueError("provide name or version_label")
        return self


class ResumeOperationQueued(BaseModel):
    resume_version_id: UUID
    background_job_id: UUID


class ResumeTexUpdate(BaseModel):
    tex_source: str = Field(min_length=1, max_length=500_000)


class ResumeVersionDetail(ResumeVersionRead):
    tex_source: str | None
    parent_version_id: UUID | None
    pdf_download_url: str | None = None
    created_at: datetime


class ResumeVersionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_version_id: UUID | None
    status: ResumeVersionStatus
    created_at: datetime
    has_pdf: bool
    name: str
    version_label: str


class ResumeVersionListItem(BaseModel):
    id: UUID
    parent_version_id: UUID | None
    status: ResumeVersionStatus
    name: str
    version_label: str
    created_at: datetime
    has_pdf: bool


class ResumeFamilyRead(BaseModel):
    id: UUID
    name: str
    versions: list[ResumeVersionListItem]


class RewriteSelection(BaseModel):
    kind: Literal["bullet", "skill"]
    id: UUID


class RewriteRequest(BaseModel):
    selections: list[RewriteSelection] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def valid_selections(self) -> Self:
        pairs = [(selection.kind, selection.id) for selection in self.selections]
        if len(set(pairs)) != len(pairs):
            raise ValueError("selections must be unique by kind and id")
        if not any(selection.kind == "bullet" for selection in self.selections):
            raise ValueError("select at least one bullet")
        return self


class RewriteQueued(BaseModel):
    resume_version_id: UUID
    background_job_id: UUID


class GuardrailFlag(BaseModel):
    term: str
    reason: Literal["number_changed", "new_technology", "unsupported_claim"]
    message: str


class ResumeBulletSelectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resume_version_id: UUID
    bullet_point_id: UUID
    original_text: str
    rewritten_text: str | None
    approved: bool
    resolved: bool
    flagged_terms: list[GuardrailFlag]
    low_effort_rewrite: bool
    section_order: int


class ResumeBulletSelectionUpdate(BaseModel):
    rewritten_text: str | None = Field(default=None, min_length=1)
    approved: bool | None = None
    revert: bool = False

    @model_validator(mode="after")
    def valid_action(self) -> Self:
        if self.revert and (self.rewritten_text is not None or self.approved is not None):
            raise ValueError("revert cannot be combined with another action")
        if not self.revert and self.rewritten_text is None and self.approved is None:
            raise ValueError("provide rewritten_text, approved, or revert")
        return self
