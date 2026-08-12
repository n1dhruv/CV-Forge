from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','done','failed')", name="job_descriptions_status_check"
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    raw_text: Mapped[str | None] = mapped_column(Text)
    source_file_url: Mapped[str | None] = mapped_column(Text)
    parsed_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'queued'"))
    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))


class JDRequirement(Base):
    __tablename__ = "jd_requirements"
    __table_args__ = (
        CheckConstraint(
            "importance in ('required','nice_to_have')", name="jd_requirements_importance_check"
        ),
        CheckConstraint(
            "technology_match_mode in ('any','all') OR technology_match_mode IS NULL",
            name="jd_requirements_technology_match_mode_check",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    jd_id: Mapped[UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    named_technologies: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    technology_match_mode: Mapped[str | None] = mapped_column(Text)


class JDActionVerb(Base):
    __tablename__ = "jd_action_verbs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    jd_id: Mapped[UUID] = mapped_column(ForeignKey("job_descriptions.id", ondelete="CASCADE"))
    verb: Mapped[str] = mapped_column(Text)


class ResumeImport(Base):
    __tablename__ = "resume_imports"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','done','failed')", name="resume_imports_status_check"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source_file_url: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'queued'"))
    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))
    committed_at: Mapped[datetime | None]


class ResumeVersion(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','rewriting','reviewing','finalized','assembling',"
            "'assembled','compiling','compiled','compile_failed')",
            name="resume_versions_status_check",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    jd_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_descriptions.id", ondelete="SET NULL")
    )
    tex_source: Mapped[str | None] = mapped_column(Text)
    pdf_storage_path: Mapped[str | None] = mapped_column(Text)
    ats_score: Mapped[Decimal | None] = mapped_column(Numeric)
    parent_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("resume_versions.id"))
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'draft'"))
    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))


class ResumeBulletSelection(Base):
    __tablename__ = "resume_bullet_selections"
    __table_args__ = (
        UniqueConstraint(
            "resume_version_id",
            "bullet_point_id",
            name="resume_bullet_selections_version_bullet_key",
        ),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    resume_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("resume_versions.id", ondelete="CASCADE")
    )
    bullet_point_id: Mapped[UUID] = mapped_column(
        ForeignKey("bullet_points.id", ondelete="CASCADE")
    )
    original_text: Mapped[str] = mapped_column(Text)
    rewritten_text: Mapped[str | None] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    resolved: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    flagged_terms: Mapped[list[dict]] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    low_effort_rewrite: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    section_order: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
