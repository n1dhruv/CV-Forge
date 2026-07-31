from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GitHubRepo(Base):
    __tablename__ = "github_repos"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    repo_name: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str] = mapped_column(Text)
    languages: Mapped[dict | None] = mapped_column(JSONB)
    readme_summary: Mapped[str | None] = mapped_column(Text)
    inferred_skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    last_synced_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class LeetCodeStats(Base):
    __tablename__ = "leetcode_stats"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(Text)
    solved_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    difficulty_distribution: Mapped[dict | None] = mapped_column(JSONB)
    last_synced_at: Mapped[datetime | None]
