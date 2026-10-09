import asyncio
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering.embedder import Embedder, embedding_text
from app.core.config import settings
from app.models.document import Document
from app.models.embedding import DocumentEmbedding
from app.models.interest import UserInterest
from app.models.source import Source
from app.models.story import Story, StoryMember
from app.models.topic import Topic
from app.ranking.scoring import Ranked, TopicProfile, match_topics, rank

MAX_CANDIDATES = 500

_topic_vectors: dict[tuple[str, str], np.ndarray] = {}


@dataclass(frozen=True)
class RankedStory:
    story: Story
    ranked: Ranked


async def topic_profiles(
    session: AsyncSession, user_id: uuid.UUID, embedder: Embedder
) -> list[TopicProfile]:
    rows = (
        await session.execute(
            select(Topic.id, Topic.name, UserInterest.weight)
            .join(UserInterest, UserInterest.topic_id == Topic.id)
            .where(UserInterest.user_id == user_id, UserInterest.is_muted.is_(False))
        )
    ).all()
    missing = [name for _, name, _ in rows if (embedder.model_name, name) not in _topic_vectors]
    if missing:
        vectors = await asyncio.to_thread(embedder.embed, missing)
        for name, vector in zip(missing, vectors, strict=True):
            _topic_vectors[(embedder.model_name, name)] = vector
    return [
        TopicProfile(topic_id, name, weight, _topic_vectors[(embedder.model_name, name)])
        for topic_id, name, weight in rows
    ]


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def rank_stories(
    session: AsyncSession,
    user_id: uuid.UUID,
    embedder: Embedder,
    now: datetime | None = None,
) -> tuple[list[RankedStory], list[RankedStory]]:
    """Return (matched, unmatched) recent stories, each sorted best-first."""
    now = now or datetime.now(UTC)
    topics = await topic_profiles(session, user_id, embedder)
    weights = {topic.topic_id: topic.weight for topic in topics}

    candidates = (
        await session.execute(
            select(Story, Document.title, Document.content_text, DocumentEmbedding.embedding)
            .join(Document, Document.id == Story.representative_document_id)
            .join(DocumentEmbedding, DocumentEmbedding.document_id == Document.id)
            .where(
                DocumentEmbedding.model == embedder.model_name,
                Story.last_seen_at >= now - timedelta(days=settings.feed_window_days),
            )
            .order_by(Story.last_seen_at.desc())
            .limit(MAX_CANDIDATES)
        )
    ).all()
    if not candidates:
        return [], []

    sources_by_story: dict[uuid.UUID, dict[str, str]] = defaultdict(dict)
    source_rows = await session.execute(
        select(StoryMember.story_id, Source.name, Source.quality_tier)
        .join(Document, Document.id == StoryMember.document_id)
        .join(Source, Source.id == Document.source_id)
        .where(StoryMember.story_id.in_([row[0].id for row in candidates]))
    )
    for story_id, source_name, tier in source_rows.all():
        sources_by_story[story_id][source_name] = tier

    matched, unmatched = [], []
    for story, title, content, raw_vector in candidates:
        vector = np.asarray(raw_vector, dtype=np.float32)
        matches = match_topics(
            embedding_text(title, content),
            vector,
            topics,
            settings.relevance_similarity_threshold,
        )
        sources = sources_by_story[story.id]
        ranked = rank(
            matches,
            weights,
            age_hours=(now - _utc(story.last_seen_at)).total_seconds() / 3600,
            source_count=len(sources),
            tiers=list(sources.values()),
        )
        (matched if matches else unmatched).append(RankedStory(story, ranked))

    matched.sort(key=lambda item: item.ranked.score, reverse=True)
    unmatched.sort(key=lambda item: item.ranked.score, reverse=True)
    return matched, unmatched
