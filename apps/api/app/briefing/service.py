import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.llm import LLMClient
from app.briefing.summarize import SourceText, summarize
from app.clustering.embedder import Embedder
from app.core.config import settings
from app.models.briefing import Brief, BriefItem, StorySummary
from app.models.document import Document
from app.models.source import Source
from app.models.story import StoryMember
from app.ranking.service import rank_stories

_UNREACHABLE = "Ollama request failed"


@dataclass
class StorySnapshot:
    headline: str
    bullets: list[dict]
    method: str
    sources: list[dict]
    errors: list[str]


def _members_key(document_ids: list[uuid.UUID]) -> str:
    return hashlib.sha256(",".join(sorted(str(i) for i in document_ids)).encode()).hexdigest()


def _source_dict(document: Document, source_name: str) -> dict:
    return {
        "document_id": str(document.id),
        "title": document.title,
        "url": document.url,
        "source_name": source_name,
        "published_at": document.published_at.isoformat() if document.published_at else None,
    }


async def _story_documents(
    session: AsyncSession, story_id: uuid.UUID
) -> list[tuple[Document, str]]:
    """Members with the representative first, then oldest to newest."""
    rows = (
        await session.execute(
            select(StoryMember.method, Document, Source.name)
            .join(Document, Document.id == StoryMember.document_id)
            .join(Source, Source.id == Document.source_id)
            .where(StoryMember.story_id == story_id)
            .order_by(Document.published_at, Document.ingested_at)
        )
    ).all()
    seed = [(doc, name) for method, doc, name in rows if method == "seed"]
    rest = [(doc, name) for method, doc, name in rows if method != "seed"]
    return seed + rest


async def summarize_story(
    session: AsyncSession,
    llm: LLMClient,
    story_id: uuid.UUID,
    use_llm: bool = True,
) -> StorySnapshot:
    members = await _story_documents(session, story_id)
    if not members:
        raise ValueError(f"story {story_id} has no members")
    key = _members_key([doc.id for doc, _ in members])
    chosen = members[: settings.summary_max_sources]
    by_id = {str(doc.id): (doc, name) for doc, name in members}

    cached = await session.get(StorySummary, story_id)
    if cached and cached.members_key == key and cached.model == llm.model_name:
        cited = [by_id[i] for i in cached.source_document_ids if i in by_id]
        if len(cited) == len(cached.source_document_ids):
            return StorySnapshot(
                headline=cached.headline,
                bullets=cached.bullets,
                method="llm",
                sources=[_source_dict(doc, name) for doc, name in cited],
                errors=[],
            )

    result = await summarize(
        llm,
        [
            SourceText(name, doc.title, doc.published_at, doc.content_text)
            for doc, name in chosen
        ],
        settings.summary_source_chars,
        max_attempts=2 if use_llm else 0,
    )
    bullets = [{"text": b.text, "citations": b.citations} for b in result.bullets]
    if result.method == "llm":
        await session.merge(
            StorySummary(
                story_id=story_id,
                members_key=key,
                model=llm.model_name,
                headline=result.headline,
                bullets=bullets,
                source_document_ids=[str(doc.id) for doc, _ in chosen],
                latency_ms=result.latency_ms,
            )
        )
    return StorySnapshot(
        headline=result.headline,
        bullets=bullets,
        method=result.method,
        sources=[_source_dict(doc, name) for doc, name in chosen],
        errors=result.errors,
    )


async def generate_brief(
    session: AsyncSession,
    user_id: uuid.UUID,
    llm: LLMClient,
    embedder: Embedder,
) -> tuple[Brief, list[BriefItem]]:
    matched, _ = await rank_stories(session, user_id, embedder)
    brief = Brief(id=uuid.uuid4(), user_id=user_id, model=llm.model_name)
    session.add(brief)

    items: list[BriefItem] = []
    errors: list[str] = []
    llm_reachable = True
    for position, ranked in enumerate(matched[: settings.brief_size]):
        snapshot = await summarize_story(session, llm, ranked.story.id, use_llm=llm_reachable)
        errors.extend(error for error in snapshot.errors if error not in errors)
        # Don't wait on a dead server once per story.
        if snapshot.errors and all(_UNREACHABLE in error for error in snapshot.errors):
            llm_reachable = False
        item = BriefItem(
            brief_id=brief.id,
            story_id=ranked.story.id,
            position=position,
            score=ranked.ranked.score,
            reasons=[
                {"kind": r.kind, "label": r.label, "contribution": r.contribution}
                for r in ranked.ranked.reasons
            ],
            headline=snapshot.headline,
            bullets=snapshot.bullets,
            method=snapshot.method,
            sources=snapshot.sources,
        )
        session.add(item)
        items.append(item)

    brief.llm_error = "; ".join(errors)[:1000] or None
    await session.commit()
    return brief, items


async def latest_brief(
    session: AsyncSession, user_id: uuid.UUID
) -> tuple[Brief, list[BriefItem]] | None:
    brief = (
        await session.execute(
            select(Brief)
            .where(Brief.user_id == user_id)
            .order_by(Brief.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if brief is None:
        return None
    items = (
        (
            await session.execute(
                select(BriefItem)
                .where(BriefItem.brief_id == brief.id)
                .order_by(BriefItem.position)
            )
        )
        .scalars()
        .all()
    )
    return brief, list(items)
