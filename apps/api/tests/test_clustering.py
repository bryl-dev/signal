from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.clustering.embedder import HashingEmbedder
from app.clustering.service import best_match, process_new_documents
from app.core.urls import sha256_text
from app.db.base import Base
from app.models.document import Document
from app.models.source import Source
from app.models.story import Story, StoryMember

NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)
LONG_BODY = (
    "Capcom detailed the next Monster Hunter Wilds title update, including a returning monster, "
    "new arena quests, balance changes for several weapons, and a festival event that runs for "
    "two weeks. The update is free for all players on every platform."
)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


async def _source(session: AsyncSession, slug: str) -> Source:
    source = Source(
        name=slug.title(),
        slug=slug,
        source_type="rss",
        homepage_url=f"https://{slug}.example.com",
        fetch_config={},
        quality_tier="blog",
        default_content_type="news",
        is_enabled=True,
    )
    session.add(source)
    await session.flush()
    return source


def _doc(source: Source, slug: str, title: str, body: str = "", hours: float = 0) -> Document:
    url = f"https://{source.slug}.example.com/{slug}"
    return Document(
        source_id=source.id,
        url=url,
        canonical_url=url,
        url_hash=sha256_text(url),
        title=title,
        published_at=NOW + timedelta(hours=hours),
        content_text=body,
        content_hash=sha256_text(body),
    )


async def _memberships(session: AsyncSession) -> dict[str, tuple]:
    rows = await session.execute(
        select(Document.title, StoryMember.story_id, StoryMember.method).join(
            StoryMember, StoryMember.document_id == Document.id
        )
    )
    return {title: (story_id, method) for title, story_id, method in rows.all()}


def test_hashing_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashingEmbedder(64)
    first, second = embedder.embed(["OpenAI ships GPT-6", "OpenAI ships GPT-6"])
    assert np.allclose(first, second)
    assert np.isclose(np.linalg.norm(first), 1.0)


def test_best_match_respects_threshold() -> None:
    candidates = np.array([[1.0, 0.0], [0.6, 0.8]], dtype=np.float32)
    assert best_match(np.array([0.6, 0.8], dtype=np.float32), candidates, 0.9) == (1, 1.0)
    index, score = best_match(np.array([0.0, 1.0], dtype=np.float32), candidates, 0.9)
    assert index is None
    assert score == pytest.approx(0.8)
    assert best_match(np.array([1.0, 0.0]), np.zeros((0, 2)), 0.5) == (None, 0.0)


async def test_groups_near_duplicates_and_keeps_distinct_events_apart(
    session: AsyncSession,
) -> None:
    polygon = await _source(session, "polygon")
    ann = await _source(session, "ann")
    session.add_all(
        [
            _doc(polygon, "a", "OpenAI releases GPT-6 with a new reasoning mode"),
            _doc(ann, "b", "OpenAI releases GPT-6 with new reasoning mode", hours=2),
            _doc(polygon, "c", "Monster Hunter Wilds title update roadmap", LONG_BODY, hours=1),
            _doc(ann, "d", "Capcom's next Wilds update detailed", LONG_BODY, hours=3),
            _doc(ann, "e", "OpenAI releases GPT-6 with a new reasoning mode, again", hours=240),
        ]
    )
    await session.commit()

    summary = await process_new_documents(session, HashingEmbedder(384), threshold=0.8)

    assert summary["clustering_error"] is None
    assert summary["embedded"] == 5
    assert summary["stories_created"] == 3
    assert summary["joined_embedding"] == 1
    assert summary["joined_content_hash"] == 1

    members = await _memberships(session)
    gpt_story, gpt_method = members["OpenAI releases GPT-6 with a new reasoning mode"]
    wilds_story, _ = members["Monster Hunter Wilds title update roadmap"]
    assert gpt_method == "seed"
    assert members["OpenAI releases GPT-6 with new reasoning mode"] == (gpt_story, "embedding")
    assert members["Capcom's next Wilds update detailed"] == (wilds_story, "content_hash")
    assert gpt_story != wilds_story
    # Same headline ten days later is outside the window, so it starts its own story.
    assert members["OpenAI releases GPT-6 with a new reasoning mode, again"][0] != gpt_story

    stories = (await session.execute(select(Story))).scalars().all()
    assert sorted(story.member_count for story in stories) == [1, 2, 2]


async def test_short_identical_bodies_do_not_merge(session: AsyncSession) -> None:
    hn = await _source(session, "hn")
    session.add_all(
        [
            _doc(hn, "a", "Show HN: A tiny Lisp in Rust"),
            _doc(hn, "b", "Ask HN: What are you reading this month?"),
        ]
    )
    await session.commit()

    summary = await process_new_documents(session, HashingEmbedder(384), threshold=0.8)

    assert summary["stories_created"] == 2
    assert summary["joined_content_hash"] == 0


async def test_recurring_templated_posts_stay_separate(session: AsyncSession) -> None:
    reddit = await _source(session, "reddit")
    session.add_all(
        [
            _doc(reddit, "w1", "Weekly Questions Megathread (week 1)", LONG_BODY),
            _doc(reddit, "w2", "Weekly Questions Megathread (week 2)", LONG_BODY, hours=168),
        ]
    )
    await session.commit()

    summary = await process_new_documents(session, HashingEmbedder(384), threshold=0.8)

    assert summary["stories_created"] == 2
    assert summary["joined_content_hash"] == 0


async def test_rerun_is_idempotent(session: AsyncSession) -> None:
    hn = await _source(session, "hn")
    session.add(_doc(hn, "a", "Show HN: A tiny Lisp in Rust"))
    await session.commit()

    embedder = HashingEmbedder(384)
    await process_new_documents(session, embedder, threshold=0.8)
    again = await process_new_documents(session, embedder, threshold=0.8)

    assert again["embedded"] == 0
    assert again["stories_created"] == 0
    assert len((await session.execute(select(Story))).scalars().all()) == 1


async def test_stories_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/stories")).status_code == 401


async def test_stories_list_empty(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "longenough"},
    )
    response = await client.get("/v1/stories")
    assert response.status_code == 200
    assert response.json()["items"] == []
