from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class LLMSettingsCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr | None = Field(default=None, min_length=1)
    embedding_provider: str | None = Field(default=None, min_length=1, max_length=50)
    embedding_model: str | None = Field(default=None, min_length=1, max_length=200)
    embedding_api_key: SecretStr | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_embedding_settings(self) -> "LLMSettingsCreate":
        provider_values = (self.embedding_provider, self.embedding_model)
        if any(provider_values) and not all(provider_values):
            raise ValueError(
                "embedding_provider and embedding_model are required together"
            )
        if self.embedding_api_key is not None and not all(provider_values):
            raise ValueError("embedding_api_key requires embedding_provider and embedding_model")
        return self


class LLMSettingsSaved(BaseModel):
    provider: str
    model: str
    embedding_provider: str | None = None
    embedding_model: str | None = None


class LLMSettingsRead(LLMSettingsSaved):
    masked_key: str
    masked_embedding_key: str | None = None


class LLMTestResult(BaseModel):
    success: bool
    error: str | None = None
