from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.jd import parse_jd_task
from app.workers.embeddings import embed_bullet_task
from app.workers.resume_imports import parse_resume_import_task


class WorkerSettings:
    functions = [parse_jd_task, embed_bullet_task, parse_resume_import_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = 180
