"""ARQ worker process. Week 1 is a heartbeat stub; ingest jobs arrive in week 2."""

from arq.connections import RedisSettings

from app.core.config import settings


async def heartbeat(ctx: dict) -> str:
    return "ok"


class WorkerSettings:
    functions = [heartbeat]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs: list = []
