import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.clustering.embedder import HashingEmbedder
from app.clustering.service import process_new_documents
from app.core.urls import sha256_text
from app.db.base import Base
from app.models.document import Document
from app.models.interest import UserInterest
from app.models.source import Source
from app.models.topic import Topic
from app.models.user import User
from app.ranking.scoring import TopicMatch, coverage_score, mentions, rank, recency_score
from app.ranking.service import rank_stories

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
TOPIC = uuid.uuid4()


def _match(kind: str) -> TopicMatch:
    strength = 1.0 if kind == "mention" else 0.8
    return TopicMatch(TOPIC, "Monster Hunter Wilds", kind, 0.7, strength)


def test_mentions_ignores_case_punctuation_and_partial_words() -> None:
    assert mentions("Granblue Fantasy Relink", "Granblue Fantasy: Relink adds Seofon")
    assert mentions("Pokémon", "23-year-old POKÉMON card sets a record")
    assert not mentions("Anthropic", "Anthropology study traces early settlements")
    assert not mentions("Grand Blue Dreaming", "Granblue Fantasy Relink sells 2 million")


def test_feature_curves() -> None:
    assert recency_score(0, 24) == 1.0
    assert recency_score(24, 24) == pytest.approx(0.5)
    assert coverage_score(1) == 0.0
    assert coverage_score(2) == pytest.approx(0.5)
    assert coverage_score(10) == 1.0


def test_rank_prefers_mentions_fresh_and_widely_covered_stories() -> None:
    weights = {TOPIC: 0.7}
    fresh_mention = rank([_match("mention")], weights, 1, 1, ["major_news"])
    fresh_semantic = rank([_match("semantic")], weights, 1, 1, ["major_news"])
    old_mention = rank([_match("mention")], weights, 72, 1, ["major_news"])
    covered = rank([_match("mention")], weights, 1, 3, ["major_news", "forum"])

    assert fresh_mention.score > fresh_semantic.score
    assert fresh_mention.score > old_mention.score
    assert covered.score > fresh_mention.score
    assert 0 < covered.score <= 1
    labels = [reason.label for reason in covered.reasons]
    assert labels[0] == "Mentions Monster Hunter Wilds"
    assert "3 sources" in labels


def test_rank_without_matches_has_no_relevance() -> None:
    ranked = rank([], {}, 1, 1, ["forum"])
    assert ranked.matches == []
    assert [reason.kind for reason in ranked.reasons] == ["recency"]


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


async def test_rank_stories_splits_matched_and_unmatched(session: AsyncSession) -> None:
    user = User(email="ada@example.com", password_hash="x", settings={})
    topic = Topic(slug="monster-hunter-wilds", name="Monster Hunter Wilds", category="gaming")
    source = Source(
        name="Polygon",
        slug="polygon",
        source_type="rss",
        homepage_url="https://polygon.com",
        fetch_config={},
        quality_tier="major_news",
        default_content_type="news",
        is_enabled=True,
    )
    session.add_all([user, topic, source])
    await session.flush()
    session.add(UserInterest(user_id=user.id, topic_id=topic.id, weight=0.7))
    for slug, title, hours_ago in [
        ("mh", "Monster Hunter Wilds title update 4 adds a new monster", 2),
        ("ssh", "OpenSSH 10.6 released", 1),
        ("old", "Monster Hunter Wilds launch week recap", 24 * 30),
    ]:
        url = f"https://polygon.com/{slug}"
        session.add(
            Document(
                source_id=source.id,
                url=url,
                canonical_url=url,
                url_hash=sha256_text(url),
                title=title,
                published_at=NOW - timedelta(hours=hours_ago),
                content_text="",
                content_hash=sha256_text(""),
            )
        )
    await session.commit()
    embedder = HashingEmbedder(384)
    await process_new_documents(session, embedder, threshold=0.99)

    matched, unmatched = await rank_stories(session, user.id, embedder, now=NOW)

    # The month-old story falls outside the feed window entirely.
    assert len(matched) == 1
    assert len(unmatched) == 1
    assert matched[0].ranked.reasons[0].label == "Mentions Monster Hunter Wilds"
    assert matched[0].ranked.score > unmatched[0].ranked.score
    assert np.isfinite(matched[0].ranked.score)


async def test_feed_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/v1/feed")).status_code == 401


async def test_feed_empty_for_new_user(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "longenough"},
    )
    response = await client.get("/v1/feed")
    assert response.status_code == 200
    assert response.json() == {"items": [], "other_items": []}
