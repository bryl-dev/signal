from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.source import Source
from app.models.story import Story, StoryMember
from app.models.user import User
from app.schemas.stories import StoryListResponse, StoryMemberResponse, StoryResponse

router = APIRouter(tags=["stories"])


async def load_stories(db: AsyncSession, stories: list[Story]) -> dict[UUID, StoryResponse]:
    """Build story payloads (lead document + members) keyed by story id."""
    if not stories:
        return {}
    rows = (
        await db.execute(
            select(StoryMember, Document, Source.name)
            .join(Document, Document.id == StoryMember.document_id)
            .join(Source, Source.id == Document.source_id)
            .where(StoryMember.story_id.in_([story.id for story in stories]))
            .order_by(Document.published_at, Document.ingested_at)
        )
    ).all()
    members_by_story: dict = defaultdict(list)
    representative: dict = {}
    for member, document, source_name in rows:
        members_by_story[member.story_id].append(
            StoryMemberResponse(
                document_id=document.id,
                title=document.title,
                url=document.url,
                source_name=source_name,
                published_at=document.published_at,
                method=member.method,
                similarity=member.similarity,
            )
        )
        if member.method == "seed":
            representative[member.story_id] = document

    payloads = {}
    for story in stories:
        lead = representative.get(story.id)
        members = members_by_story[story.id]
        if lead is None or not members:
            continue
        payloads[story.id] = StoryResponse(
            id=story.id,
            title=lead.title,
            url=lead.url,
            excerpt=lead.content_text[:240],
            first_seen_at=story.first_seen_at,
            last_seen_at=story.last_seen_at,
            source_count=len({member.source_name for member in members}),
            members=members,
        )
    return payloads


@router.get("/stories", response_model=StoryListResponse)
async def list_stories(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=30, ge=1, le=100),
) -> StoryListResponse:
    stories = (
        (await db.execute(select(Story).order_by(Story.last_seen_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    payloads = await load_stories(db, list(stories))
    return StoryListResponse(items=[payloads[s.id] for s in stories if s.id in payloads])
