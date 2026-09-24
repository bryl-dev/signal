from pathlib import Path

from app.ingest.adapters.rss import RssAdapter
from app.models.source import Source

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "rss" / "sample.xml"


def test_rss_parse_and_normalize() -> None:
    adapter = RssAdapter()
    items = adapter.parse(FIXTURE.read_bytes())
    assert len(items) == 2
    assert items[0].title == "New paper on RAG agents"

    source = Source(
        name="Fixture",
        slug="fixture",
        source_type="rss",
        homepage_url="https://example.com",
        default_content_type="news",
    )
    drafts = [adapter.normalize(item, source) for item in items]
    assert drafts[0].canonical_url == "https://example.com/posts/rag-agents"
    assert drafts[1].canonical_url == "https://example.com/posts/rag-agents"
    assert "<b>" not in drafts[0].content_text
    assert "short summary" in drafts[0].content_text
