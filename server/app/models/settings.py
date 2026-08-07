from uuid import UUID

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserLLMSettings(TimestampMixin, Base):
    __tablename__ = "user_llm_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    encrypted_api_key: Mapped[str] = mapped_column(Text)
    embedding_provider: Mapped[str | None] = mapped_column(Text)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    encrypted_embedding_api_key: Mapped[str | None] = mapped_column(Text)
