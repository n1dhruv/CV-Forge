from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.user import User

PROFILE_TEXT_FIELDS = (
    "full_name",
    "contact_email",
    "phone",
    "location",
    "linkedin_url",
    "github_url",
    "leetcode_url",
    "portfolio_url",
)
PROFILE_LINK_FIELDS = ("linkedin_url", "github_url", "leetcode_url", "portfolio_url")


class _ProfileFields(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    contact_email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=160)
    linkedin_url: str | None = Field(default=None, max_length=2048)
    github_url: str | None = Field(default=None, max_length=2048)
    leetcode_url: str | None = Field(default=None, max_length=2048)
    portfolio_url: str | None = Field(default=None, max_length=2048)

    @field_validator(*PROFILE_TEXT_FIELDS, mode="before")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator(*PROFILE_LINK_FIELDS)
    @classmethod
    def validate_web_link(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL must use http or https")
        return value


class ProfileUpdate(_ProfileFields):
    @model_validator(mode="after")
    def has_change(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("provide at least one profile field")
        return self


class ProfileImport(_ProfileFields):
    def non_empty_values(self) -> dict[str, str]:
        return {
            field: value
            for field, value in self.model_dump().items()
            if isinstance(value, str) and value
        }


class ProfileRead(_ProfileFields):
    model_config = ConfigDict(from_attributes=True)

    contact_email: str = Field(max_length=254)

    @classmethod
    def from_user(cls, user: User) -> "ProfileRead":
        values = {field: getattr(user, field) for field in PROFILE_TEXT_FIELDS}
        values["contact_email"] = values["contact_email"] or user.email
        return cls.model_validate(values)
