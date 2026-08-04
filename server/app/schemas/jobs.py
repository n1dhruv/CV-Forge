from typing import Literal

from pydantic import BaseModel


class BackgroundJobRead(BaseModel):
    status: Literal["queued", "running", "done", "failed"]
    result: dict | None
    error: str | None
