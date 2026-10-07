"""ARQ worker. Ingest can also be triggered from POST /v1/ingest."""

from arq.connections import RedisSettings

from app.clustering.service import process_new_documents
from app.core.config import settings
from app.core.tls import use_system_trust_store
from app.db.session import SessionLocal
from app.ingest.pipeline import ingest_all

use_system_trust_store()


async def heartbeat(ctx: dict) -> str:
    return "ok"


async def ingest_all_job(ctx: dict) -> dict:
    async with SessionLocal() as session:
        summary = await ingest_all(session)
        summary.update(await process_new_documents(session))
        return summary


class WorkerSettings:
    functions = [heartbeat, ingest_all_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    cron_jobs: list = []
