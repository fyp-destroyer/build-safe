"""Pydantic v2 request/response schemas for the chat transcript endpoints.

A transcript row is either plain text or a positional marker for the risk
card. `text` is required for `kind="text"` and must be absent for
`kind="risk_card"` — the card's contents come from the assessment at read
time, never from the transcript (see models/chat_message.py).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MessageRole = Literal["user", "assistant"]
MessageKind = Literal["text", "risk_card"]


class ChatMessageIn(BaseModel):
    """One message to append to a job's transcript."""

    role: MessageRole
    kind: MessageKind = "text"
    text: str | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def _check_text_matches_kind(self) -> "ChatMessageIn":
        if self.kind == "text" and not (self.text or "").strip():
            raise ValueError("text is required when kind is 'text'")
        if self.kind == "risk_card" and self.text:
            # Refused rather than ignored: a risk_card row carrying text is a
            # caller trying to persist a copy of the verdict, which is exactly
            # what must not happen (models/chat_message.py explains why).
            raise ValueError("risk_card messages must not carry text")
        return self


class ChatMessagesAppendRequest(BaseModel):
    """POST /jobs/{id}/messages body — a batch, since the UI emits several
    messages per turn and one request per message would race on ordering."""

    messages: list[ChatMessageIn] = Field(min_length=1, max_length=100)


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    role: MessageRole
    kind: MessageKind
    text: str | None
    position: int
    created_at: datetime


class ChatMessagesOut(BaseModel):
    messages: list[ChatMessageOut]
