from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BackgroundJob(TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','running','done','failed')", name="background_jobs_status_check"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'queued'"))
    result: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
