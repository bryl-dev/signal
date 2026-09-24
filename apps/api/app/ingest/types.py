from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawItem:
    url: str
    title: str
    content: str = ""
    author: str | None = None
    published_at: datetime | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class DocumentDraft:
    url: str
    canonical_url: str
    title: str
    content_text: str
    author: str | None
    published_at: datetime | None
    content_type: str
    extra: dict
