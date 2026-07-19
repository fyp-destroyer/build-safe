"""422 validation errors must use the structured error shape and must not
themselves crash while serializing field-level detail (regression: a custom
Pydantic field_validator's raised ValueError landed in `ctx.error` and was
not JSON-serializable — see main.py's validation_error_handler)."""

import pytest

pytestmark = pytest.mark.anyio


async def test_invalid_email_returns_422_structured_error(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "short", "name": "a"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["fields"], list)
    assert any(f["loc"][-1] == "email" for f in body["error"]["fields"])


async def test_missing_required_field_returns_422(client):
    resp = await client.post("/auth/register", json={"email": "valid@example.com"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_invalid_category_returns_422(client):
    token_resp = await client.post(
        "/auth/register",
        json={"email": "catcheck@example.com", "password": "password123", "name": "Cat"},
    )
    headers = {"Authorization": f"Bearer {token_resp.json()['access_token']}"}

    resp = await client.post(
        "/jobs",
        json={
            "description": "something",
            "category": "not_a_real_category",
            "skill_level": "beginner",
            "urgency": "low",
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
