from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import struct_time

import feedparser
import httpx

from app.core.urls import canonicalize_url, strip_html
from app.ingest.fetch import fetch_bytes
from app.ingest.types import DocumentDraft, RawItem
from app.models.source import Source


class RssAdapter:
    source_type = "rss"

    def __init__(self, content_type: str | None = None) -> None:
        self._content_type = content_type

    async def fetch(self, config: dict, client: httpx.AsyncClient) -> list[RawItem]:
        feed_url = config["feed_url"]
        allowed_hosts = config.get("allowed_hosts") or []
        check_dns = config.get("check_dns", True)
        body = await fetch_bytes(client, feed_url, allowed_hosts, check_dns=check_dns)
        return self.parse(body, max_items=int(config.get("max_items", 25)))

    def parse(self, body: bytes, max_items: int = 25) -> list[RawItem]:
        parsed = feedparser.parse(body)
        items: list[RawItem] = []
        for entry in parsed.entries[:max_items]:
            link = getattr(entry, "link", None)
            title = getattr(entry, "title", None)
            if not link or not title:
                continue
            content = ""
            if getattr(entry, "summary", None):
                content = entry.summary
            elif getattr(entry, "description", None):
                content = entry.description
            items.append(
                RawItem(
                    url=link,
                    title=title,
                    content=content,
                    author=getattr(entry, "author", None) or None,
                    published_at=_entry_published(entry),
                    extra={"guid": getattr(entry, "id", None)},
                )
            )
        return items

    def normalize(self, raw: RawItem, source: Source) -> DocumentDraft:
        return DocumentDraft(
            url=raw.url,
            canonical_url=canonicalize_url(raw.url),
            title=strip_html(raw.title)[:500],
            content_text=strip_html(raw.content)[:20_000],
            author=raw.author,
            published_at=raw.published_at,
            content_type=self._content_type or source.default_content_type,
            extra=raw.extra,
        )


def _entry_published(entry: object) -> datetime | None:
    parsed_struct = getattr(entry, "published_parsed", None)
    if parsed_struct is None:
        parsed_struct = getattr(entry, "updated_parsed", None)
    if isinstance(parsed_struct, struct_time):
        return datetime(*parsed_struct[:6], tzinfo=UTC)
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not raw:
        return None
    try:
        value = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
