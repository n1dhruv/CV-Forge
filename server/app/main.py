from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.skill_bank import router as skill_bank_router
from app.api.storage import router as storage_router
from app.api.webhooks import router as webhook_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    redis = Redis.from_url(settings.redis_url)
    await redis.ping()
    app.state.redis = redis
    yield
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="CV-Forge API", version="0.1.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(skill_bank_router)
app.include_router(storage_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
