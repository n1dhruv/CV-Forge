from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuid_generate_v4()"))
    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True)
    email: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    skill_bank_items: Mapped[list["SkillBankItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


from app.models.skill_bank import SkillBankItem  # noqa: E402
