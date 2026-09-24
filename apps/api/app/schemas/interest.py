from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

TopicCategoryId = Literal["ai", "gaming", "anime"]


class TopicResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    category: str
    description: str | None = None


class TopicCategoryResponse(BaseModel):
    id: str
    name: str
    topics: list[TopicResponse]


class TopicCatalogResponse(BaseModel):
    categories: list[TopicCategoryResponse]


class InterestItem(BaseModel):
    topic_id: UUID
    slug: str
    name: str
    category: str
    weight: float
    is_muted: bool
    source: str


class InterestsResponse(BaseModel):
    items: list[InterestItem]
    onboarded: bool


class UpdateInterestsRequest(BaseModel):
    topic_ids: list[UUID] = Field(min_length=1)


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: TopicCategoryId
