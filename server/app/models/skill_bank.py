from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Text, text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class SkillBankItem(TimestampMixin, Base):
    __tablename__ = "skill_bank_items"
    __table_args__ = (
        CheckConstraint(
            "type in ('experience','project','skill','education','certification')",
            name="skill_bank_items_type_check",
        ),
        CheckConstraint(
            "source in ('manual','resume_import','github')",
            name="skill_bank_items_source_check",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    org: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    raw_text: Mapped[str | None] = mapped_column(Text)
    skill_category: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql_text("'{}'::text[]"))
    source: Mapped[str] = mapped_column(Text, server_default=sql_text("'manual'"))
    user: Mapped["User"] = relationship(back_populates="skill_bank_items")
    bullet_points: Mapped[list["BulletPoint"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BulletPoint.display_order",
    )


class BulletPoint(TimestampMixin, Base):
    __tablename__ = "bullet_points"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sql_text("uuid_generate_v4()")
    )
    item_id: Mapped[UUID] = mapped_column(ForeignKey("skill_bank_items.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql_text("'{}'::text[]"))
    metrics: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    item: Mapped[SkillBankItem] = relationship(back_populates="bullet_points")
