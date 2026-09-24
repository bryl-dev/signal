from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.ingest.pipeline import ingest_source
from app.models.document import Document
from app.models.source import Source

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "rss" / "sample.xml"


async def _auth(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "longenough"},
    )


@pytest.mark.asyncio
async def test_ingest_fixture_feed_upserts_once() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    xml = FIXTURE.read_bytes()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=xml)

    async with factory() as session:
        source = Source(
            name="Fixture Feed",
            slug="fixture-feed",
            source_type="rss",
            homepage_url="https://example.com",
            fetch_config={
                "feed_url": "https://feeds.example.com/ai",
                "allowed_hosts": ["feeds.example.com"],
                "check_dns": False,
                "max_items": 10,
            },
            quality_tier="blog",
            default_content_type="news",
            is_enabled=True,
        )
        session.add(source)
        await session.commit()
        await session.refresh(source)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            run = await ingest_source(session, source, http)

        assert run.status == "ok"
        assert run.items_fetched == 2
        rows = (await session.execute(select(Document))).scalars().all()
        assert len(rows) == 1
        assert rows[0].canonical_url == "https://example.com/posts/rag-agents"

    await engine.dispose()


@pytest.mark.asyncio
async def test_documents_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/documents")).status_code == 401


@pytest.mark.asyncio
async def test_documents_list_empty(client: AsyncClient) -> None:
    await _auth(client)
    response = await client.get("/v1/documents")
    assert response.status_code == 200
    assert response.json()["items"] == []
