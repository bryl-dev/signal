from pathlib import Path

from app.ingest.adapters.rss import RssAdapter
from app.models.source import Source

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "rss"
FIXTURE = FIXTURES / "sample.xml"


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


def test_steam_news_feed() -> None:
    adapter = RssAdapter()
    items = adapter.parse((FIXTURES / "steam_news.xml").read_bytes())
    assert len(items) == 2

    source = Source(
        name="Steam News",
        slug="steam-news",
        source_type="rss",
        homepage_url="https://store.steampowered.com/news/",
        default_content_type="news",
    )
    draft = adapter.normalize(items[0], source)
    assert draft.title.startswith("Sonic Racing: CrossWorlds")
    assert draft.canonical_url == (
        "https://store.steampowered.com/news/app/2486820/view/677385962174548895"
    )
    assert draft.published_at is not None
    assert draft.published_at.year == 2026
    # Steam escapes its BBCode-rendered HTML; none of it should survive normalization.
    assert "bb_paragraph" not in draft.content_text
    assert "&lt;" not in draft.content_text
    assert "Year Two will be going live November 3, 2026" in draft.content_text
