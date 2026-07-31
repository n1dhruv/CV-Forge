from pydantic import BaseModel, Field


class StoragePathRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024, pattern=r"^[^/].*")


class SignedUrlResponse(BaseModel):
    path: str
    signed_url: str
    token: str | None = None
