from datetime import date, datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ItemType = Literal["experience", "project", "skill", "education", "certification"]
ItemSource = Literal["manual", "resume_import", "github"]


class ItemLink(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=40)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL must use http or https")
        return value


def validate_item_links(item_type: ItemType, links: list[ItemLink]) -> list[ItemLink]:
    if links and item_type not in {"project", "certification"}:
        raise ValueError("links may be added to only projects and certifications")
    limit = 2 if item_type == "project" else 1
    if item_type in {"project", "certification"} and len(links) > limit:
        raise ValueError(f"{item_type} accepts at most {limit} link{'s' if limit > 1 else ''}")
    return links


class BulletCreate(BaseModel):
    text: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    metrics: str | None = None
    display_order: int = 0


class BulletUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    metrics: str | None = None
    display_order: int | None = None


class BulletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    item_id: UUID
    text: str
    tags: list[str]
    metrics: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime


class ItemCreate(BaseModel):
    type: ItemType
    title: str = Field(min_length=1)
    org: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    raw_text: str | None = None
    tags: list[str] = Field(default_factory=list)
    links: list[ItemLink] = Field(default_factory=list)
    skill_category: str | None = Field(default=None, max_length=80)

    @field_validator("skill_category", mode="before")
    @classmethod
    def normalize_skill_category(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def category_only_for_skills(self) -> "ItemCreate":
        if self.type != "skill":
            self.skill_category = None
        validate_item_links(self.type, self.links)
        return self


class ItemUpdate(BaseModel):
    type: ItemType | None = None
    title: str | None = Field(default=None, min_length=1)
    org: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    raw_text: str | None = None
    tags: list[str] | None = None
    links: list[ItemLink] | None = None
    skill_category: str | None = Field(default=None, max_length=80)

    @field_validator("skill_category", mode="before")
    @classmethod
    def normalize_skill_category(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    type: ItemType
    title: str
    org: str | None
    start_date: date | None
    end_date: date | None
    raw_text: str | None
    tags: list[str]
    links: list[ItemLink]
    skill_category: str | None
    source: ItemSource
    created_at: datetime
    updated_at: datetime


class ItemDetail(ItemRead):
    bullet_points: list[BulletRead]


class ReembedQueued(BaseModel):
    items_queued: int
    bullets_queued: int
    failed: int
