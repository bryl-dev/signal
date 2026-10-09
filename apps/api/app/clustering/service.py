"""Embed new documents and group same-event coverage into stories.

Grouping is deliberately conservative: a leftover duplicate is a minor annoyance, but two
different events merged into one story hides news. A document joins a story only if
  1. its body is byte-identical to a member's (and long enough to be meaningful), or
  2. its embedding is within the similarity threshold of the story's representative
     (first) document, inside the time window.
Comparing against the representative rather than any member prevents chain drift.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import numpy as np
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering.embedder import Embedder, embedding_text, get_embedder
from app.core.config import settings
from app.models.document import Document
from app.models.embedding import DocumentEmbedding
from app.models.story import Story, StoryMember

logger = structlog.get_logger()


def best_match(
    vector: np.ndarray, candidates: np.ndarray, threshold: float
) -> tuple[int | None, float]:
    """Index of the most similar candidate row if it clears the threshold, plus its score."""
    if candidates.shape[0] == 0:
        return None, 0.0
    scores = candidates @ vector
    index = int(np.argmax(scores))
    score = float(scores[index])
    return (index if score >= threshold else None), score


def _utc(value: datetime) -> datetime:
    # SQLite drops tzinfo on read; Postgres keeps it.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _event_time(document: Document) -> datetime:
    return _utc(document.published_at or document.ingested_at)


async def embed_pending(session: AsyncSession, embedder: Embedder, batch_size: int = 64) -> int:
    total = 0
    while True:
        rows = (
            await session.execute(
                select(Document.id, Document.title, Document.content_text)
                .outerjoin(DocumentEmbedding, DocumentEmbedding.document_id == Document.id)
                .where(
                    or_(
                        DocumentEmbedding.document_id.is_(None),
                        DocumentEmbedding.model != embedder.model_name,
                    )
                )
                .limit(batch_size)
            )
        ).all()
        if not rows:
            return total
        texts = [embedding_text(row.title, row.content_text) for row in rows]
        vectors = await asyncio.to_thread(embedder.embed, texts)
        for row, vector in zip(rows, vectors, strict=True):
            await session.merge(
                DocumentEmbedding(
                    document_id=row.id,
                    model=embedder.model_name,
                    embedding=vector.tolist(),
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()
        total += len(rows)


async def _find_story(
    session: AsyncSession,
    document: Document,
    vector: np.ndarray,
    when: datetime,
    model_name: str,
    threshold: float,
    window: timedelta,
) -> tuple[Story | None, str | None, float | None]:
    # Recurring posts (weekly megathreads) reuse templated bodies, so identical text
    # still has to fall inside the time window.
    in_window = (Story.last_seen_at >= when - window, Story.first_seen_at <= when + window)

    if len(document.content_text) >= settings.dedup_min_content_chars:
        same_text = (
            await session.execute(
                select(Story)
                .join(StoryMember, StoryMember.story_id == Story.id)
                .join(Document, Document.id == StoryMember.document_id)
                .where(Document.content_hash == document.content_hash, *in_window)
                .limit(1)
            )
        ).scalar_one_or_none()
        if same_text is not None:
            return same_text, "content_hash", 1.0

    candidates = (
        await session.execute(
            select(Story, DocumentEmbedding.embedding)
            .join(
                DocumentEmbedding,
                DocumentEmbedding.document_id == Story.representative_document_id,
            )
            .where(DocumentEmbedding.model == model_name, *in_window)
        )
    ).all()
    if not candidates:
        return None, None, None
    matrix = np.asarray([row[1] for row in candidates], dtype=np.float32)
    index, score = best_match(vector, matrix, threshold)
    if index is None:
        return None, None, None
    return candidates[index][0], "embedding", round(score, 4)


async def cluster_pending(
    session: AsyncSession,
    model_name: str,
    threshold: float,
    window: timedelta,
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(Document, DocumentEmbedding.embedding)
            .join(DocumentEmbedding, DocumentEmbedding.document_id == Document.id)
            .outerjoin(StoryMember, StoryMember.document_id == Document.id)
            .where(StoryMember.document_id.is_(None), DocumentEmbedding.model == model_name)
            .order_by(func.coalesce(Document.published_at, Document.ingested_at), Document.id)
        )
    ).all()

    counts = {"stories_created": 0, "joined_content_hash": 0, "joined_embedding": 0}
    for document, raw_vector in rows:
        when = _event_time(document)
        vector = np.asarray(raw_vector, dtype=np.float32)
        story, method, similarity = await _find_story(
            session, document, vector, when, model_name, threshold, window
        )
        if story is None:
            story = Story(
                id=uuid.uuid4(),
                representative_document_id=document.id,
                first_seen_at=when,
                last_seen_at=when,
                member_count=1,
            )
            session.add(story)
            method = "seed"
            counts["stories_created"] += 1
        else:
            story.member_count += 1
            story.first_seen_at = min(_utc(story.first_seen_at), when)
            story.last_seen_at = max(_utc(story.last_seen_at), when)
            counts[f"joined_{method}"] += 1
        session.add(
            StoryMember(
                document_id=document.id,
                story_id=story.id,
                method=method,
                similarity=similarity,
            )
        )
        await session.flush()
    await session.commit()
    return counts


async def process_new_documents(
    session: AsyncSession,
    embedder: Embedder | None = None,
    threshold: float | None = None,
) -> dict:
    summary: dict = {
        "embedded": 0,
        "stories_created": 0,
        "joined_content_hash": 0,
        "joined_embedding": 0,
        "clustering_error": None,
    }
    try:
        if embedder is None:
            embedder = await asyncio.to_thread(get_embedder)
        summary["embedded"] = await embed_pending(session, embedder)
        summary.update(
            await cluster_pending(
                session,
                embedder.model_name,
                settings.cluster_similarity_threshold if threshold is None else threshold,
                timedelta(hours=settings.cluster_window_hours),
            )
        )
    except Exception as exc:
        await session.rollback()
        logger.warning("clustering_failed", error=str(exc))
        summary["clustering_error"] = str(exc)[:500]
    return summary
