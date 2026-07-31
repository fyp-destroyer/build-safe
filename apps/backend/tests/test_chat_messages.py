"""Chat transcript persistence — GET/POST /jobs/{id}/messages.

Two things matter here beyond "it stores text": ownership (a transcript is
user content and must 404 for anyone else, like every other route) and
ordering (a conversation rendered out of order is worse than no transcript).

The third is a safety boundary: a `risk_card` message is a positional marker
and must not be allowed to carry text, because that would be a second copy
of a verdict that can drift from the assessment of record.
"""

import pytest

from tests.conftest import register_and_login

pytestmark = pytest.mark.anyio


async def _auth_headers(client, email: str) -> dict:
    token = await register_and_login(client, email)
    return {"Authorization": f"Bearer {token}"}


async def _make_job(client, headers, description="paint the hallway") -> str:
    resp = await client.post(
        "/jobs",
        json={"description": description, "category": "painting", "skill_level": "beginner"},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_messages_round_trip_in_conversation_order(client):
    headers = await _auth_headers(client, "chat1@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.post(
        f"/jobs/{job_id}/messages",
        json={
            "messages": [
                {"role": "user", "text": "paint the hallway"},
                {"role": "assistant", "text": "What's your experience level?"},
                {"role": "user", "text": "Beginner"},
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 201

    got = await client.get(f"/jobs/{job_id}/messages", headers=headers)
    assert got.status_code == 200
    messages = got.json()["messages"]
    assert [m["text"] for m in messages] == [
        "paint the hallway",
        "What's your experience level?",
        "Beginner",
    ]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    # Positions are assigned server-side and strictly increasing.
    assert [m["position"] for m in messages] == sorted(m["position"] for m in messages)
    assert len(set(m["position"] for m in messages)) == 3


async def test_appending_continues_after_existing_messages(client):
    """A second batch must not restart numbering — that would interleave it
    with the first when sorted, scrambling the conversation."""
    headers = await _auth_headers(client, "chat2@example.com")
    job_id = await _make_job(client, headers)

    for text in ("first", "second"):
        resp = await client.post(
            f"/jobs/{job_id}/messages",
            json={"messages": [{"role": "user", "text": text}]},
            headers=headers,
        )
        assert resp.status_code == 201

    messages = (await client.get(f"/jobs/{job_id}/messages", headers=headers)).json()["messages"]
    assert [m["text"] for m in messages] == ["first", "second"]
    assert messages[0]["position"] < messages[1]["position"]


async def test_risk_card_message_stores_no_verdict(client):
    """A risk_card row marks WHERE the card goes, nothing more. The card is
    re-rendered from the assessment, so the transcript can never show a risk
    level that has drifted from the assessment of record."""
    headers = await _auth_headers(client, "chat3@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "assistant", "kind": "risk_card"}]},
        headers=headers,
    )
    assert resp.status_code == 201

    message = (await client.get(f"/jobs/{job_id}/messages", headers=headers)).json()["messages"][0]
    assert message["kind"] == "risk_card"
    assert message["text"] is None


async def test_risk_card_carrying_text_is_rejected(client):
    """Refused, not silently dropped: a caller sending this is trying to
    persist a copy of the verdict."""
    headers = await _auth_headers(client, "chat4@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "assistant", "kind": "risk_card", "text": "Risk level 5"}]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_empty_text_message_is_rejected(client):
    headers = await _auth_headers(client, "chat5@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "user", "text": "   "}]},
        headers=headers,
    )
    assert resp.status_code == 422


async def test_transcript_is_private_to_its_owner(client):
    """Another user must not read or write someone else's conversation —
    same 404 as every other job-scoped route, never leaking existence."""
    headers_a = await _auth_headers(client, "chat_owner@example.com")
    headers_b = await _auth_headers(client, "chat_intruder@example.com")
    job_id = await _make_job(client, headers_a)

    await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "user", "text": "private"}]},
        headers=headers_a,
    )

    assert (await client.get(f"/jobs/{job_id}/messages", headers=headers_b)).status_code == 404
    write = await client.post(
        f"/jobs/{job_id}/messages",
        json={"messages": [{"role": "user", "text": "injected"}]},
        headers=headers_b,
    )
    assert write.status_code == 404

    # And the owner's transcript is untouched by the attempt.
    messages = (await client.get(f"/jobs/{job_id}/messages", headers=headers_a)).json()["messages"]
    assert [m["text"] for m in messages] == ["private"]


async def test_messages_require_authentication(client):
    headers = await _auth_headers(client, "chat6@example.com")
    job_id = await _make_job(client, headers)

    assert (await client.get(f"/jobs/{job_id}/messages")).status_code == 401


async def test_empty_transcript_returns_empty_list(client):
    """Jobs created before this feature existed have no transcript; that must
    read as "nothing stored", not an error — the UI falls back to rebuilding
    an approximation for those."""
    headers = await _auth_headers(client, "chat7@example.com")
    job_id = await _make_job(client, headers)

    resp = await client.get(f"/jobs/{job_id}/messages", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["messages"] == []
