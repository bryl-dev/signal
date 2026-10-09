from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    url: str
    source_name: str
    source_type: str
    author: str | None
    published_at: datetime | None
    ingested_at: datetime
    content_type: str
    excerpt: str


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]


class IngestResponse(BaseModel):
    sources: int
    fetched: int
    upserted: int
    errors: list[dict]
    embedded: int = 0
    stories_created: int = 0
    joined_content_hash: int = 0
    joined_embedding: int = 0
    clustering_error: str | None = None
