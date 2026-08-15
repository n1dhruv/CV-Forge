from pydantic import BaseModel, ConfigDict, Field, SecretStr


class LLMSettingsCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr | None = Field(default=None, min_length=1)


class LLMSettingsSaved(BaseModel):
    provider: str
    model: str


class LLMSettingsRead(LLMSettingsSaved):
    masked_key: str


class LLMTestResult(BaseModel):
    success: bool
    error: str | None = None
