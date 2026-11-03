from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.feed import RankReason


class BriefBullet(BaseModel):
    text: str
    citations: list[int]


class BriefSource(BaseModel):
    document_id: UUID
    title: str
    url: str
    source_name: str
    published_at: datetime | None


class BriefItemResponse(BaseModel):
    story_id: UUID | None
    position: int
    score: float
    reasons: list[RankReason]
    headline: str
    bullets: list[BriefBullet]
    method: str
    sources: list[BriefSource]


class BriefResponse(BaseModel):
    id: UUID
    created_at: datetime
    model: str
    llm_error: str | None
    items: list[BriefItemResponse]


class BriefEnvelope(BaseModel):
    brief: BriefResponse | None
