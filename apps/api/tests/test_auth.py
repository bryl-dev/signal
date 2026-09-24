import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, email: str = "ada@example.com") -> dict:
    response = await client.post(
        "/v1/auth/register",
        json={"email": email, "password": "longenough"},
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_register_sets_cookies_and_me(client: AsyncClient) -> None:
    body = await _register(client)
    assert body["email"] == "ada@example.com"
    assert body["onboarded"] is False
    assert client.cookies.get("access_token")
    assert client.cookies.get("refresh_token")

    me = await client.get("/v1/me")
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await _register(client)
    response = await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "longenough"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_and_logout(client: AsyncClient) -> None:
    await _register(client)
    await client.post("/v1/auth/logout")
    assert (await client.get("/v1/me")).status_code == 401

    bad = await client.post(
        "/v1/auth/login",
        json={"email": "ada@example.com", "password": "nope-nope"},
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/v1/auth/login",
        json={"email": "Ada@example.com", "password": "longenough"},
    )
    assert ok.status_code == 200
    assert (await client.get("/v1/me")).status_code == 200


@pytest.mark.asyncio
async def test_refresh(client: AsyncClient) -> None:
    await _register(client)
    client.cookies.pop("access_token", None)
    refreshed = await client.post("/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert (await client.get("/v1/me")).status_code == 200


@pytest.mark.asyncio
async def test_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/register",
        json={"email": "ada@example.com", "password": "short"},
    )
    assert response.status_code == 422
