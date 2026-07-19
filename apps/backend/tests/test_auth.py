"""Auth flow: register + login happy path, duplicate email 409."""

import pytest

pytestmark = pytest.mark.anyio


async def test_register_returns_token_and_user(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "password123", "name": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "alice@example.com"
    assert body["user"]["name"] == "Alice"


async def test_login_happy_path(client):
    await client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "password123", "name": "Bob"},
    )

    resp = await client.post(
        "/auth/login", json={"email": "bob@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "bob@example.com"


async def test_login_wrong_password_401(client):
    await client.post(
        "/auth/register",
        json={"email": "carol@example.com", "password": "password123", "name": "Carol"},
    )

    resp = await client.post(
        "/auth/login", json={"email": "carol@example.com", "password": "wrongpassword"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_register_duplicate_email_409(client):
    payload = {"email": "dupe@example.com", "password": "password123", "name": "Dupe"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "email_already_registered"


async def test_protected_route_without_token_401(client):
    resp = await client.post(
        "/jobs",
        json={
            "description": "paint the fence",
            "category": "painting",
            "skill_level": "beginner",
            "urgency": "low",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"
