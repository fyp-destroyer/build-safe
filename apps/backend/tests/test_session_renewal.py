"""Session longevity — long-lived tokens plus sliding renewal.

The user's requirement was "whenever I open this I am always logged in".
Two mechanisms deliver that, and both are tested here:

  1. a session lasts 30 days rather than the old 60 minutes, and
  2. any authenticated request made past the halfway mark hands back a fresh
     token, so an active user's clock keeps resetting.

The security boundary still has to hold: renewal must never resurrect an
already-expired token, and must never issue a token for anyone but the
caller.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from core.config import get_settings
from core.security import _ALGORITHM, create_access_token, decode_access_token
from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio

settings = get_settings()


def _token_with_age(subject: str, *, issued_minutes_ago: int, lifetime_minutes: int) -> str:
    """A token that was issued in the past, so renewal logic can be exercised
    without waiting or monkeypatching the clock."""
    issued = datetime.now(timezone.utc) - timedelta(minutes=issued_minutes_ago)
    payload = {
        "sub": subject,
        "iat": issued,
        "exp": issued + timedelta(minutes=lifetime_minutes),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=_ALGORITHM)


def test_default_session_is_long_lived():
    """A 60-minute session was the root cause of being logged out mid-use."""
    assert settings.JWT_EXPIRES_MINUTES >= 60 * 24 * 7

    claims = decode_access_token(create_access_token("11111111-1111-1111-1111-111111111111"))
    lifetime_days = (claims["exp"] - claims["iat"]) / 86400
    assert lifetime_days >= 7


async def test_fresh_token_is_not_renewed(client):
    """No churn on every request — only tokens past halfway get replaced."""
    token = await register_and_login(client, "renew_fresh@example.com")

    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "X-Refreshed-Token" not in resp.headers


async def test_token_past_halfway_is_renewed_and_still_works(client):
    """The mechanism that makes an active session never end: a request made
    past the halfway mark returns a fresh token, which itself authenticates."""
    token = await register_and_login(client, "renew_old@example.com")
    subject = decode_access_token(token)["sub"]

    # Same user, but issued long enough ago to be past halfway and still valid.
    aged = _token_with_age(subject, issued_minutes_ago=40, lifetime_minutes=60)

    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {aged}"})
    assert resp.status_code == 200
    renewed = resp.headers.get("X-Refreshed-Token")
    assert renewed and renewed != aged

    # The renewed token belongs to the same user and has a later expiry...
    old_claims, new_claims = decode_access_token(aged), decode_access_token(renewed)
    assert new_claims["sub"] == old_claims["sub"] == subject
    assert new_claims["exp"] > old_claims["exp"]

    # ...and actually authenticates, which is the whole point.
    assert (
        await client.get("/jobs", headers={"Authorization": f"Bearer {renewed}"})
    ).status_code == 200


async def test_renewed_token_header_is_exposed_to_the_browser(client):
    """Browsers hide non-safelisted response headers from JS unless the
    server exposes them. Without this the frontend can never read the renewed
    token and sessions would still expire — a silent failure."""
    token = await register_and_login(client, "renew_cors@example.com")
    subject = decode_access_token(token)["sub"]
    aged = _token_with_age(subject, issued_minutes_ago=40, lifetime_minutes=60)

    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {aged}"})
    assert "X-Refreshed-Token" in resp.headers.get("Access-Control-Expose-Headers", "")


async def test_expired_token_is_rejected_not_renewed(client):
    """The boundary that must not move: renewal extends a LIVE session, it
    never resurrects a dead one. An expired token is still a 401."""
    token = await register_and_login(client, "renew_expired@example.com")
    subject = decode_access_token(token)["sub"]

    expired = _token_with_age(subject, issued_minutes_ago=120, lifetime_minutes=60)

    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401
    assert "X-Refreshed-Token" not in resp.headers


async def test_tampered_token_is_rejected_not_renewed(client):
    """A token signed with the wrong key must never be renewed into a valid
    one — that would turn the renewal convenience into a forgery oracle."""
    forged = jwt.encode(
        {
            "sub": "22222222-2222-2222-2222-222222222222",
            "iat": datetime.now(timezone.utc) - timedelta(minutes=40),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
        },
        "not-the-real-secret",
        algorithm=_ALGORITHM,
    )

    resp = await client.get("/jobs", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401
    assert "X-Refreshed-Token" not in resp.headers
