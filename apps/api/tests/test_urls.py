from app.core.urls import canonicalize_url, sha256_text, strip_html


def test_canonicalize_strips_tracking_and_www() -> None:
    raw = "http://www.Example.com/posts/rag-agents/?utm_source=rss&ref=hn"
    assert canonicalize_url(raw) == "https://example.com/posts/rag-agents"


def test_same_story_same_hash() -> None:
    left = canonicalize_url("https://example.com/posts/rag-agents?utm_campaign=x")
    right = canonicalize_url("https://www.example.com/posts/rag-agents/")
    assert sha256_text(left) == sha256_text(right)


def test_strip_html() -> None:
    assert strip_html("A <b>short</b> summary") == "A short summary"
