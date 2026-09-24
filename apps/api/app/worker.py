"""ARQ worker. Ingest can also be triggered from POST /v1/ingest."""

from arq.connections import RedisSettings

from app.core.config import settings
from app.db.session import SessionLocal
from app.ingest.pipeline import ingest_all


async def heartbeat(ctx: dict) -> str:
    return "ok"


async def ingest_all_job(ctx: dict) -> dict:
    async with SessionLocal() as session:
        return await ingest_all(session)


class WorkerSettings:
    functions = [heartbeat, ingest_all_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs: list = []
