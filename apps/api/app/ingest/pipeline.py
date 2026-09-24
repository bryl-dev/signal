import asyncio
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.urls import sha256_text
from app.ingest.adapters import get_adapter
from app.models.document import Document
from app.models.ingestion import IngestionRun
from app.models.source import Source

logger = structlog.get_logger()


async def ingest_all(session: AsyncSession) -> dict:
    result = await session.execute(select(Source).where(Source.is_enabled.is_(True)))
    sources = result.scalars().all()
    summary = {"sources": 0, "fetched": 0, "upserted": 0, "errors": []}
    async with httpx.AsyncClient(
        headers={"User-Agent": "Signal/0.1 (+https://github.com/bryl-dev/signal)"},
        verify=settings.ingest_tls_verify,
    ) as client:
        for index, source in enumerate(sources):
            if index:
                await asyncio.sleep(1)
            run = await ingest_source(session, source, client)
            summary["sources"] += 1
            summary["fetched"] += run.items_fetched
            summary["upserted"] += run.items_upserted
            if run.error:
                summary["errors"].append({"source": source.slug, "error": run.error})
    return summary


async def ingest_source(
    session: AsyncSession,
    source: Source,
    client: httpx.AsyncClient,
) -> IngestionRun:
    run = IngestionRun(source_id=source.id, status="running")
    session.add(run)
    await session.flush()

    try:
        adapter = get_adapter(source.source_type)
        raw_items = await adapter.fetch(source.fetch_config, client)
        upserted = 0
        for raw in raw_items:
            draft = adapter.normalize(raw, source)
            url_hash = sha256_text(draft.canonical_url)
            content_hash = sha256_text(draft.content_text)
            existing = await session.execute(select(Document).where(Document.url_hash == url_hash))
            document = existing.scalar_one_or_none()
            if document is None:
                session.add(
                    Document(
                        source_id=source.id,
                        url=draft.url,
                        canonical_url=draft.canonical_url,
                        url_hash=url_hash,
                        title=draft.title,
                        author=draft.author,
                        published_at=draft.published_at,
                        content_text=draft.content_text,
                        content_hash=content_hash,
                        content_type=draft.content_type,
                        extra=draft.extra,
                    )
                )
                upserted += 1
            elif document.content_hash != content_hash:
                document.title = draft.title
                document.content_text = draft.content_text
                document.content_hash = content_hash
                document.author = draft.author
                document.published_at = draft.published_at
                document.extra = draft.extra
                upserted += 1
        run.items_fetched = len(raw_items)
        run.items_upserted = upserted
        run.status = "ok"
    except Exception as exc:
        logger.warning("ingest_failed", source=source.slug, error=str(exc))
        run.status = "error"
        run.error = str(exc)[:2000]
    finally:
        run.finished_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
    return run
