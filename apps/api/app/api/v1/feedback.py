import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering.embedder import get_embedder
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.feedback import StoryFeedback
from app.models.story import Story, StoryMember
from app.models.user import User
from app.ranking.service import match_story
from app.schemas.feed import FeedbackRequest, FeedbackResponse

router = APIRouter(tags=["feedback"])


@router.put("/feedback", response_model=FeedbackResponse)
async def set_feedback(
    payload: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    story = await db.get(Story, payload.story_id)
    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found")

    # One vote per story: clear votes on any member, not just the current lead document.
    member_ids = select(StoryMember.document_id).where(StoryMember.story_id == story.id)
    await db.execute(
        delete(StoryFeedback).where(
            StoryFeedback.user_id == user.id, StoryFeedback.document_id.in_(member_ids)
        )
    )
    topic_ids = []
    if payload.value:
        embedder = await asyncio.to_thread(get_embedder)
        topic_ids = await match_story(db, user.id, story, embedder)
        db.add(
            StoryFeedback(
                user_id=user.id,
                document_id=story.representative_document_id,
                value=payload.value,
                topic_ids=[str(topic_id) for topic_id in topic_ids],
            )
        )
    await db.commit()
    return FeedbackResponse(story_id=story.id, value=payload.value, topic_ids=topic_ids)
