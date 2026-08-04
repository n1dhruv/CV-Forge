from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.jd import parse_jd_task


class WorkerSettings:
    functions = [parse_jd_task]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_tries = 1
    job_timeout = 180
