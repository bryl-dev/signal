from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StoryMemberResponse(BaseModel):
    document_id: UUID
    title: str
    url: str
    source_name: str
    published_at: datetime | None
    method: str
    similarity: float | None


class StoryResponse(BaseModel):
    id: UUID
    title: str
    url: str
    excerpt: str
    first_seen_at: datetime
    last_seen_at: datetime
    source_count: int
    members: list[StoryMemberResponse]


class StoryListResponse(BaseModel):
    items: list[StoryResponse]
