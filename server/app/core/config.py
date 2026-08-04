from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    database_url: str = Field(alias="DATABASE_URL")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_storage_bucket_resumes: str = Field(alias="SUPABASE_STORAGE_BUCKET_RESUMES")
    supabase_storage_bucket_jd_uploads: str = Field(alias="SUPABASE_STORAGE_BUCKET_JD_UPLOADS")
    redis_url: str = Field(alias="REDIS_URL")
    clerk_secret_key: SecretStr = Field(alias="CLERK_SECRET_KEY")
    clerk_jwks_url: str = Field(alias="CLERK_JWKS_URL")
    clerk_issuer: str | None = Field(default=None, alias="CLERK_ISSUER")
    clerk_webhook_signing_secret: SecretStr = Field(alias="CLERK_WEBHOOK_SIGNING_SECRET")
    encryption_key: SecretStr = Field(alias="ENCRYPTION_KEY")
    embedding_model: str = Field(alias="EMBEDDING_MODEL")
    github_client_id: str = Field(alias="GITHUB_CLIENT_ID")
    github_client_secret: SecretStr = Field(alias="GITHUB_CLIENT_SECRET")
    tectonic_binary_path: str = Field(alias="TECTONIC_BINARY_PATH")
    environment: str = Field(alias="ENVIRONMENT")

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: SecretStr) -> SecretStr:
        Fernet(value.get_secret_value().encode())
        return value

    @computed_field
    @property
    def effective_clerk_issuer(self) -> str:
        if self.clerk_issuer:
            return self.clerk_issuer.rstrip("/")
        parts = urlsplit(self.clerk_jwks_url)
        return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
