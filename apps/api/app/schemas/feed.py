from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.stories import StoryResponse


class MatchedTopic(BaseModel):
    topic_id: UUID
    name: str
    kind: str
    similarity: float


class RankReason(BaseModel):
    kind: str
    label: str
    contribution: float


class FeedItem(BaseModel):
    story: StoryResponse
    score: float
    matched_topics: list[MatchedTopic]
    reasons: list[RankReason]
    feedback: int = 0


class FeedResponse(BaseModel):
    items: list[FeedItem]
    other_items: list[FeedItem]


class FeedbackRequest(BaseModel):
    story_id: UUID
    # 1 = more like this, -1 = hide and less like this, 0 = clear.
    value: Literal[-1, 0, 1]


class FeedbackResponse(BaseModel):
    story_id: UUID
    value: int
    topic_ids: list[UUID]
