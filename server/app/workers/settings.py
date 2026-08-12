from arq.connections import RedisSettings
from arq.worker import func

from app.core.config import get_settings
from app.workers.jd import parse_jd_task
from app.workers.embeddings import embed_bullet_task, embed_item_task
from app.workers.resume_imports import parse_resume_import_task
from app.workers.match import match_jd_task
from app.workers.rewrite import rewrite_bullets_task
from app.workers.resume_assembly import assemble_resume_task
from app.workers.resume_compile import compile_resume_task


class WorkerSettings:
    functions = [
        parse_jd_task,
        embed_bullet_task,
        embed_item_task,
        parse_resume_import_task,
        func(match_jd_task, timeout=600),
        func(rewrite_bullets_task, timeout=1800),
        assemble_resume_task,
        func(compile_resume_task, timeout=get_settings().latex_compile_timeout_seconds + 30),
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = 180
