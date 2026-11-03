import uuid
from collections.abc import AsyncGenerator

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering.embedder import HashingEmbedder
from app.clustering.service import process_new_documents
from app.core.config import settings
from app.core.urls import sha256_text
from app.db.seed import topic_id
from app.db.session import get_db
from app.main import app
from app.models.document import Document
from app.models.source import Source
from app.ranking.scoring import (
    FeedbackSignal,
    TopicMatch,
    TopicProfile,
    match_topics,
    mentions,
    rank,
)

ANTHROPIC = str(topic_id("anthropic"))
OTHERS = [str(topic_id(slug)) for slug in ["llms", "openai", "rag", "nintendo"]]
TOPIC = uuid.uuid4()


def test_short_phrases_match_case_sensitively() -> None:
    assert mentions("LoL", "LoL patch 26.20 notes")
    assert not mentions("LoL", "lol, this patch broke everything")
    assert mentions("RAG", "Why RAG pipelines fail")
    assert not mentions("RAG", "Rag doll physics in Godot")
    assert mentions("Claude", "CLAUDE can now control your browser")


def test_alias_mentions_name_the_alias_and_the_topic() -> None:
    profile = TopicProfile(TOPIC, "Anthropic", 0.7, np.zeros(4), aliases=("Claude",))
    matches = match_topics("Claude can now control your browser", np.zeros(4), [profile], 0.64)
    assert [(m.kind, m.via) for m in matches] == [("mention", "Claude")]
    ranked = rank(matches, {TOPIC: 0.7}, 1, 1, ["major_news"])
    assert ranked.reasons[0].label == "Mentions Claude (Anthropic)"


def test_feedback_signals_change_relevance_and_explain_it() -> None:
    plain = rank([], {}, 1, 1, ["forum"])
    liked = rank([], {}, 1, 1, ["forum"], liked=FeedbackSignal("OpenSSH 10.6 released", 0.9))
    assert liked.score > plain.score
    assert liked.reasons[0].label == "Like “OpenSSH 10.6 released”, which you liked"
    assert liked.reasons[0].contribution > 0

    match = TopicMatch(TOPIC, "Anthropic", "mention", 0.7, 1.0)
    normal = rank([match], {TOPIC: 0.7}, 1, 1, ["forum"], votes_by_topic={TOPIC: 2})
    penalized = rank(
        [match], {TOPIC: 0.7}, 1, 1, ["forum"], disliked=FeedbackSignal("Claude outage", 0.85)
    )
    assert penalized.score < normal.score
    assert "Boosted by your votes on Anthropic" in [r.label for r in normal.reasons]
    hid = next(r for r in penalized.reasons if "which you hid" in r.label)
    assert hid.contribution < 0


async def _session() -> AsyncGenerator[AsyncSession, None]:
    async for db in app.dependency_overrides[get_db]():
        yield db


async def _seed_stories(titles: list[str]) -> None:
    async for db in _session():
        source = Source(
            name="Hacker News",
            slug="hn",
            source_type="hn",
            homepage_url="https://news.ycombinator.com",
            fetch_config={},
            quality_tier="aggregator",
            default_content_type="news",
            is_enabled=True,
        )
        db.add(source)
        await db.flush()
        for title in titles:
            url = f"https://example.com/{sha256_text(title)[:10]}"
            db.add(
                Document(
                    source_id=source.id,
                    url=url,
                    canonical_url=url,
                    url_hash=sha256_text(url),
                    title=title,
                    content_text="",
                    content_hash=sha256_text(title),
                )
            )
        await db.commit()
        await process_new_documents(db, HashingEmbedder(settings.embedding_dim), threshold=0.99)


async def _register(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register", json={"email": "ada@example.com", "password": "longenough"}
    )
    await client.put("/v1/me/interests", json={"topic_ids": [ANTHROPIC, *OTHERS]})


def _titles(items: list[dict]) -> list[str]:
    return [item["story"]["title"] for item in items]


async def test_feedback_hides_boosts_and_adjusts_weights(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "feedback_similarity_threshold", 0.5)
    await _register(client)
    await _seed_stories(
        [
            "Claude can now control your browser",
            "OpenSSH 10.6 released",
            "OpenSSH 10.6 released today",
        ]
    )
    feed = (await client.get("/v1/feed")).json()
    assert _titles(feed["items"]) == ["Claude can now control your browser"]
    assert feed["items"][0]["reasons"][0]["label"] == "Mentions Claude (Anthropic)"
    claude = feed["items"][0]["story"]["id"]
    ssh = next(
        i["story"]["id"] for i in feed["other_items"] if i["story"]["title"].endswith("released")
    )

    hidden = await client.put("/v1/feedback", json={"story_id": claude, "value": -1})
    assert hidden.json()["topic_ids"] == [ANTHROPIC]
    feed = (await client.get("/v1/feed")).json()
    assert claude not in [i["story"]["id"] for i in feed["items"] + feed["other_items"]]
    interests = (await client.get("/v1/me/interests")).json()["items"]
    anthropic = next(i for i in interests if i["topic_id"] == ANTHROPIC)
    assert (anthropic["votes"], anthropic["effective_weight"]) == (-1, 0.65)

    await client.put("/v1/feedback", json={"story_id": ssh, "value": 1})
    feed = (await client.get("/v1/feed")).json()
    by_title = {i["story"]["title"]: i for i in feed["items"]}
    assert by_title["OpenSSH 10.6 released"]["feedback"] == 1
    assert by_title["OpenSSH 10.6 released"]["reasons"][0]["label"] == "You liked this"
    assert by_title["OpenSSH 10.6 released today"]["reasons"][0]["label"] == (
        "Like “OpenSSH 10.6 released”, which you liked"
    )

    await client.put("/v1/feedback", json={"story_id": claude, "value": 0})
    feed = (await client.get("/v1/feed")).json()
    assert "Claude can now control your browser" in _titles(feed["items"])


async def test_feedback_requires_auth_and_a_real_story(client: AsyncClient) -> None:
    body = {"story_id": str(uuid.uuid4()), "value": 1}
    assert (await client.put("/v1/feedback", json=body)).status_code == 401
    await _register(client)
    assert (await client.put("/v1/feedback", json=body)).status_code == 404
    assert (await client.put("/v1/feedback", json={**body, "value": 2})).status_code == 422


async def test_aliases_survive_resaving_interests(client: AsyncClient) -> None:
    await _register(client)
    updated = await client.patch(
        f"/v1/me/interests/{ANTHROPIC}", json={"aliases": ["  Claude  Code ", "claude code"]}
    )
    assert updated.status_code == 200
    assert updated.json()["aliases"] == ["Claude Code"]
    assert "Claude" in updated.json()["topic_aliases"]

    assert (
        await client.patch(f"/v1/me/interests/{ANTHROPIC}", json={"aliases": ["x"]})
    ).status_code == 422
    assert (
        await client.patch(f"/v1/me/interests/{uuid.uuid4()}", json={"aliases": []})
    ).status_code == 404

    await client.put("/v1/me/interests", json={"topic_ids": [ANTHROPIC, *OTHERS]})
    items = (await client.get("/v1/me/interests")).json()["items"]
    assert next(i for i in items if i["topic_id"] == ANTHROPIC)["aliases"] == ["Claude Code"]
