from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TopicCategoryId = Literal["ai", "gaming", "anime"]


class TopicResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    category: str
    description: str | None = None
    aliases: list[str] = []


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
    # weight after adjusting for the user's votes on stories in this topic.
    effective_weight: float
    votes: int
    is_muted: bool
    source: str
    aliases: list[str]
    topic_aliases: list[str]


class InterestsResponse(BaseModel):
    items: list[InterestItem]
    onboarded: bool


class UpdateInterestsRequest(BaseModel):
    topic_ids: list[UUID] = Field(min_length=1)


class UpdateInterestRequest(BaseModel):
    aliases: list[str] = Field(max_length=10)

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, value: list[str]) -> list[str]:
        cleaned: dict[str, str] = {}
        for alias in value:
            alias = " ".join(alias.split())
            if len(alias) < 2 or len(alias) > 60:
                raise ValueError("Each alias must be 2 to 60 characters.")
            cleaned.setdefault(alias.casefold(), alias)
        return list(cleaned.values())


class CreateTopicRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: TopicCategoryId
