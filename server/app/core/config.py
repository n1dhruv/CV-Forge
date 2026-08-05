from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    database_url: str = Field(alias="DATABASE_URL")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_secret_key: SecretStr = Field(alias="SUPABASE_SECRET_KEY")
    supabase_storage_bucket_resumes: str = Field(alias="SUPABASE_STORAGE_BUCKET_RESUMES")
    supabase_storage_bucket_jd_uploads: str = Field(alias="SUPABASE_STORAGE_BUCKET_JD_UPLOADS")
    redis_url: str = Field(alias="REDIS_URL")
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
    def supabase_auth_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @computed_field
    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_auth_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
