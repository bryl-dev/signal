import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient) -> None:
    await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "longenough"},
    )


@pytest.mark.asyncio
async def test_topic_catalog(client: AsyncClient) -> None:
    response = await client.get("/v1/topics")
    assert response.status_code == 200
    categories = response.json()["categories"]
    assert [c["id"] for c in categories] == ["ai", "gaming", "anime"]
    slugs = [topic["slug"] for cat in categories for topic in cat["topics"]]
    assert "ai-agents" in slugs
    assert "elden-ring" in slugs
    assert "one-piece" in slugs


@pytest.mark.asyncio
async def test_replace_interests_requires_auth(client: AsyncClient) -> None:
    response = await client.put("/v1/me/interests", json={"topic_ids": []})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_onboarding_interests(client: AsyncClient) -> None:
    await _auth(client)
    catalog = (await client.get("/v1/topics")).json()
    topic_ids = [topic["id"] for cat in catalog["categories"] for topic in cat["topics"]]

    too_few = await client.put("/v1/me/interests", json={"topic_ids": topic_ids[:3]})
    assert too_few.status_code == 422

    saved = await client.put("/v1/me/interests", json={"topic_ids": topic_ids[:5]})
    assert saved.status_code == 200
    body = saved.json()
    assert body["onboarded"] is True
    assert len(body["items"]) == 5

    me = await client.get("/v1/me")
    assert me.json()["onboarded"] is True

    listed = await client.get("/v1/me/interests")
    assert {item["topic_id"] for item in listed.json()["items"]} == set(topic_ids[:5])


@pytest.mark.asyncio
async def test_create_custom_topic(client: AsyncClient) -> None:
    await _auth(client)
    created = await client.post(
        "/v1/topics",
        json={"name": "Granblue Fantasy Relink", "category": "gaming"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["slug"] == "granblue-fantasy-relink"
    assert body["category"] == "gaming"

    again = await client.post(
        "/v1/topics",
        json={"name": "granblue fantasy relink", "category": "gaming"},
    )
    assert again.json()["id"] == body["id"]

    catalog = await client.get("/v1/topics")
    gaming = next(cat for cat in catalog.json()["categories"] if cat["id"] == "gaming")
    assert any(topic["slug"] == "granblue-fantasy-relink" for topic in gaming["topics"])


@pytest.mark.asyncio
async def test_create_topic_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/topics",
        json={"name": "Monster Hunter Wilds", "category": "gaming"},
    )
    assert response.status_code == 401
