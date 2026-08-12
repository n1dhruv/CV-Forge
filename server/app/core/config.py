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
    supabase_storage_bucket_resume_imports: str = Field(
        alias="SUPABASE_STORAGE_BUCKET_RESUME_IMPORTS"
    )
    redis_url: str = Field(alias="REDIS_URL")
    encryption_key: SecretStr = Field(alias="ENCRYPTION_KEY")
    embedding_model: str = Field(alias="EMBEDDING_MODEL")
    pinecone_api_key: SecretStr = Field(alias="PINECONE_API_KEY", min_length=1)
    pinecone_index_name: str = Field(alias="PINECONE_INDEX_NAME", min_length=1)
    pinecone_host: str = Field(alias="PINECONE_HOST", min_length=1)
    pinecone_sparse_index_name: str = Field(alias="PINECONE_SPARSE_INDEX_NAME", min_length=1)
    openrouter_api_key: SecretStr = Field(alias="OPENROUTER_API_KEY", min_length=1)
    openrouter_rerank_model: str = Field(
        default="nvidia/llama-nemotron-rerank-vl-1b-v2:free",
        alias="OPENROUTER_RERANK_MODEL",
        min_length=1,
    )
    github_client_id: str = Field(alias="GITHUB_CLIENT_ID")
    github_client_secret: SecretStr = Field(alias="GITHUB_CLIENT_SECRET")
    tectonic_binary_path: str = Field(alias="TECTONIC_BINARY_PATH")
    latex_compile_timeout_seconds: int = Field(
        default=30, alias="LATEX_COMPILE_TIMEOUT_SECONDS", gt=0
    )
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
