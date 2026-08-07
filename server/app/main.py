from contextlib import asynccontextmanager
from typing import AsyncIterator

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.jd import router as jd_router
from app.api.jobs import router as jobs_router
from app.api.match import router as match_router
from app.api.resume_imports import router as resume_imports_router
from app.api.skill_bank import router as skill_bank_router
from app.api.settings import router as llm_settings_router
from app.api.storage import router as storage_router
from app.core.config import get_settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.ping()
    app.state.redis = redis
    app.state.arq = redis
    yield
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title="CV-Forge API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skill_bank_router)
app.include_router(storage_router)
app.include_router(llm_settings_router)
app.include_router(jd_router)
app.include_router(jobs_router)
app.include_router(match_router)
app.include_router(resume_imports_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
