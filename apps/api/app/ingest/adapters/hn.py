import json
from datetime import UTC, datetime

import httpx

from app.core.urls import canonicalize_url, strip_html
from app.ingest.fetch import fetch_bytes
from app.ingest.types import DocumentDraft, RawItem
from app.models.source import Source

DEFAULT_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
DEFAULT_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"


class HackerNewsAdapter:
    source_type = "hn"

    async def fetch(self, config: dict, client: httpx.AsyncClient) -> list[RawItem]:
        allowed = config.get("allowed_hosts") or ["hacker-news.firebaseio.com"]
        check_dns = config.get("check_dns", True)
        top_url = config.get("top_stories_url", DEFAULT_TOP)
        item_template = config.get("item_url_template", DEFAULT_ITEM)
        max_items = int(config.get("max_items", 20))

        raw_ids = await fetch_bytes(client, top_url, allowed, check_dns=check_dns)
        story_ids = json.loads(raw_ids)
        if not isinstance(story_ids, list):
            return []

        items: list[RawItem] = []
        for story_id in story_ids[:max_items]:
            item_url = item_template.format(id=story_id)
            payload = await fetch_bytes(client, item_url, allowed, check_dns=check_dns)
            data = json.loads(payload)
            if not isinstance(data, dict) or data.get("type") != "story":
                continue
            title = data.get("title")
            url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
            if not title:
                continue
            published = None
            if data.get("time"):
                published = datetime.fromtimestamp(int(data["time"]), tz=UTC)
            items.append(
                RawItem(
                    url=url,
                    title=title,
                    content=data.get("text") or "",
                    author=data.get("by"),
                    published_at=published,
                    extra={"hn_id": story_id, "score": data.get("score")},
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
            content_type=source.default_content_type,
            extra=raw.extra,
        )
