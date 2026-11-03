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
from app.models.feedback import StoryFeedback
from app.models.interest import UserInterest
from app.models.source import Source
from app.models.story import Story, StoryMember
from app.models.topic import Topic
from app.ranking.scoring import FeedbackSignal, Ranked, TopicProfile, match_topics, rank

MAX_CANDIDATES = 500

_topic_vectors: dict[tuple[str, str], np.ndarray] = {}


@dataclass(frozen=True)
class RankedStory:
    story: Story
    ranked: Ranked
    # The user's vote on this story: 1, 0, or -1 (hidden stories are left out of the feed).
    feedback: int = 0


@dataclass(frozen=True)
class _Vote:
    value: int
    story_id: uuid.UUID | None
    title: str
    vector: np.ndarray | None
    created_at: datetime


def effective_weight(base: float, votes: int) -> float:
    adjusted = base + settings.feedback_weight_step * votes
    return min(settings.feedback_weight_max, max(settings.feedback_weight_min, adjusted))


async def topic_votes(session: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = await session.execute(
        select(StoryFeedback.value, StoryFeedback.topic_ids).where(
            StoryFeedback.user_id == user_id
        )
    )
    votes: dict[uuid.UUID, int] = defaultdict(int)
    for value, topic_ids in rows.all():
        for topic_id in topic_ids:
            votes[uuid.UUID(topic_id)] += value
    return votes


async def topic_profiles(
    session: AsyncSession, user_id: uuid.UUID, embedder: Embedder
) -> list[TopicProfile]:
    rows = (
        await session.execute(
            select(Topic, UserInterest)
            .join(UserInterest, UserInterest.topic_id == Topic.id)
            .where(UserInterest.user_id == user_id, UserInterest.is_muted.is_(False))
        )
    ).all()
    missing = [t.name for t, _ in rows if (embedder.model_name, t.name) not in _topic_vectors]
    if missing:
        vectors = await asyncio.to_thread(embedder.embed, missing)
        for name, vector in zip(missing, vectors, strict=True):
            _topic_vectors[(embedder.model_name, name)] = vector
    votes = await topic_votes(session, user_id)
    return [
        TopicProfile(
            topic.id,
            topic.name,
            effective_weight(interest.weight, votes.get(topic.id, 0)),
            _topic_vectors[(embedder.model_name, topic.name)],
            aliases=tuple(dict.fromkeys([*topic.aliases, *interest.aliases])),
            votes=votes.get(topic.id, 0),
        )
        for topic, interest in rows
    ]


async def _votes(session: AsyncSession, user_id: uuid.UUID, model_name: str) -> list[_Vote]:
    rows = await session.execute(
        select(
            StoryFeedback.value,
            StoryFeedback.created_at,
            StoryMember.story_id,
            Document.title,
            DocumentEmbedding.embedding,
        )
        .join(Document, Document.id == StoryFeedback.document_id)
        .outerjoin(StoryMember, StoryMember.document_id == StoryFeedback.document_id)
        .outerjoin(
            DocumentEmbedding,
            (DocumentEmbedding.document_id == StoryFeedback.document_id)
            & (DocumentEmbedding.model == model_name),
        )
        .where(StoryFeedback.user_id == user_id)
    )
    return [
        _Vote(
            value,
            story_id,
            title,
            None if raw is None else np.asarray(raw, dtype=np.float32),
            _utc(created_at),
        )
        for value, created_at, story_id, title, raw in rows.all()
    ]


def _closest(votes: list[_Vote], vector: np.ndarray, threshold: float) -> FeedbackSignal | None:
    best: _Vote | None = None
    best_similarity = threshold
    for vote in votes:
        similarity = float(vote.vector @ vector)
        if similarity >= best_similarity:
            best, best_similarity = vote, similarity
    return FeedbackSignal(best.title, best_similarity) if best else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def match_story(
    session: AsyncSession, user_id: uuid.UUID, story: Story, embedder: Embedder
) -> list[uuid.UUID]:
    """Topic ids the story matches for this user right now (recorded with a vote)."""
    row = (
        await session.execute(
            select(Document.title, Document.content_text, DocumentEmbedding.embedding)
            .join(DocumentEmbedding, DocumentEmbedding.document_id == Document.id)
            .where(
                Document.id == story.representative_document_id,
                DocumentEmbedding.model == embedder.model_name,
            )
        )
    ).one_or_none()
    if row is None:
        return []
    title, content, raw = row
    topics = await topic_profiles(session, user_id, embedder)
    matches = match_topics(
        embedding_text(title, content),
        np.asarray(raw, dtype=np.float32),
        topics,
        settings.relevance_similarity_threshold,
    )
    return [match.topic_id for match in matches]


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
    votes_by_topic = {topic.topic_id: topic.votes for topic in topics}

    votes = await _votes(session, user_id, embedder.model_name)
    hidden = {vote.story_id for vote in votes if vote.value < 0 and vote.story_id}
    liked_stories = {vote.story_id for vote in votes if vote.value > 0 and vote.story_id}
    recent = now - timedelta(days=settings.feedback_window_days)
    usable = [vote for vote in votes if vote.vector is not None and vote.created_at >= recent]

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
    candidates = [row for row in candidates if row[0].id not in hidden]
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

    threshold = settings.feedback_similarity_threshold
    matched, unmatched = [], []
    for story, title, content, raw_vector in candidates:
        vector = np.asarray(raw_vector, dtype=np.float32)
        matches = match_topics(
            embedding_text(title, content),
            vector,
            topics,
            settings.relevance_similarity_threshold,
        )
        others = [vote for vote in usable if vote.story_id != story.id]
        if story.id in liked_stories:
            liked = FeedbackSignal(None, 1.0)
        else:
            liked = _closest([v for v in others if v.value > 0], vector, threshold)
        disliked = _closest([v for v in others if v.value < 0], vector, threshold)
        sources = sources_by_story[story.id]
        ranked = rank(
            matches,
            weights,
            age_hours=(now - _utc(story.last_seen_at)).total_seconds() / 3600,
            source_count=len(sources),
            tiers=list(sources.values()),
            liked=liked,
            disliked=disliked,
            votes_by_topic=votes_by_topic,
        )
        item = RankedStory(story, ranked, feedback=1 if story.id in liked_stories else 0)
        (matched if matches or liked else unmatched).append(item)

    matched.sort(key=lambda item: item.ranked.score, reverse=True)
    unmatched.sort(key=lambda item: item.ranked.score, reverse=True)
    return matched, unmatched
