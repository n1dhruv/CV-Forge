from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RewriteRequest(BaseModel):
    bullet_point_ids: list[UUID] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_bullets(self) -> Self:
        if len(set(self.bullet_point_ids)) != len(self.bullet_point_ids):
            raise ValueError("bullet_point_ids must be unique")
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
