from typing import Protocol

import httpx

from app.ingest.types import DocumentDraft, RawItem
from app.models.source import Source


class SourceAdapter(Protocol):
    source_type: str

    async def fetch(self, config: dict, client: httpx.AsyncClient) -> list[RawItem]: ...

    def normalize(self, raw: RawItem, source: Source) -> DocumentDraft: ...
