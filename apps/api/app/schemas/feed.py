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


class FeedResponse(BaseModel):
    items: list[FeedItem]
    other_items: list[FeedItem]
