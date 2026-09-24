from app.ingest.adapters.base import SourceAdapter
from app.ingest.adapters.hn import HackerNewsAdapter
from app.ingest.adapters.rss import RssAdapter

ADAPTERS: dict[str, SourceAdapter] = {
    "rss": RssAdapter(),
    "youtube_rss": RssAdapter(content_type="video"),
    "hn": HackerNewsAdapter(),
}


def get_adapter(source_type: str) -> SourceAdapter:
    try:
        return ADAPTERS[source_type]
    except KeyError as exc:
        raise ValueError(f"Unknown source type: {source_type}") from exc
