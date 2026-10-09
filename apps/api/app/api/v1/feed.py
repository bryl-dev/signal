import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.stories import load_stories
from app.clustering.embedder import get_embedder
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.ranking.service import RankedStory, rank_stories
from app.schemas.feed import FeedItem, FeedResponse, MatchedTopic, RankReason

router = APIRouter(tags=["feed"])


@router.get("/feed", response_model=FeedResponse)
async def get_feed(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=30, ge=1, le=100),
    other_limit: int = Query(default=20, ge=0, le=100),
) -> FeedResponse:
    embedder = await asyncio.to_thread(get_embedder)
    matched, unmatched = await rank_stories(db, user.id, embedder)
    matched, unmatched = matched[:limit], unmatched[:other_limit]
    payloads = await load_stories(db, [item.story for item in matched + unmatched])

    def to_item(item: RankedStory) -> FeedItem | None:
        story = payloads.get(item.story.id)
        if story is None:
            return None
        return FeedItem(
            story=story,
            score=item.ranked.score,
            matched_topics=[
                MatchedTopic(
                    topic_id=match.topic_id,
                    name=match.name,
                    kind=match.kind,
                    similarity=round(match.similarity, 3),
                )
                for match in item.ranked.matches
            ],
            reasons=[
                RankReason(kind=r.kind, label=r.label, contribution=r.contribution)
                for r in item.ranked.reasons
            ],
        )

    return FeedResponse(
        items=[built for item in matched if (built := to_item(item))],
        other_items=[built for item in unmatched if (built := to_item(item))],
    )
