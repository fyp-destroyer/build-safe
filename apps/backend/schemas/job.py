"""Pydantic v2 request/response schemas for /jobs.

`TASK_CATEGORIES` locks the 9 categories from phases.md Phase 1.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TASK_CATEGORIES = (
    "electrical",
    "plumbing",
    "carpentry",
    "masonry",
    "painting",
    "tiling",
    "hvac",
    "roofing",
    "general",
)

TaskCategory = Literal[
    "electrical",
    "plumbing",
    "carpentry",
    "masonry",
    "painting",
    "tiling",
    "hvac",
    "roofing",
    "general",
]

JobStatus = Literal["pending_followup", "ready_to_assess", "assessed", "failed"]


class JobCreateRequest(BaseModel):
    """POST /jobs body.

    `category` is optional: when omitted, the frontend's conversational
    intake sends only free-text `description`, and the backend infers the
    category via Gemini tagging (a fixed, closed 9-value classification —
    rules.md §4, see ai/rule_engine/llm_assist.tag_category). When provided
    explicitly, it's used as-is (still validated against the fixed Literal).
    """

    description: str = Field(min_length=1, max_length=5000)
    category: TaskCategory | None = None
    # Optional since 2026-08-02, and no longer collected by the chat flow —
    # the same retirement `urgency` got, for the same reason: nothing
    # consumes it any more, so asking cost the user a step in a safety flow
    # and bought nothing.
    #
    # It stopped being a classifier feature when the seed data was rebalanced
    # (ml/rebalance_skill.py): with skill and label made independent, its
    # coefficient mass fell to the weakest block in the model, and the
    # prediction became identical across all three values. The one rule that
    # used it, `electrical_work_by_beginner`, is gone — `fixed_wiring_work`
    # now carries its floor of 3 for everyone, which is the more honest
    # number anyway given srs.md §3 concedes the input is unverifiable
    # self-report.
    #
    # Still accepted, and the column retained (nullable), so existing clients
    # and rows are unaffected and the change is reversible.
    skill_level: str | None = Field(default=None, max_length=50)
    # Optional, and no longer collected by the chat flow. Nothing consumes
    # it: it is excluded from the classifier as a non-safety feature
    # (ml/train_baseline.py) and the rule engine ignores it. Kept on the API
    # so existing clients and srs.md FR-02 are not silently broken - see
    # srs.md FR-02's note.
    urgency: str | None = Field(default=None, max_length=50)


class JobFollowupRequest(BaseModel):
    """PATCH /jobs/{id}/followup body — free-form answers keyed by field
    name. Real per-category question schema is a Phase 5 concern; until
    then this is intentionally open-ended (mirrors Job.followup_answers)."""

    answers: dict = Field(default_factory=dict)


class FollowupPrompt(BaseModel):
    """A single still-missing safety-critical follow-up, with Gemini-phrased
    question wording for an already-hardcoded field (rules.md §4 - the LLM
    only supplies wording, never which field or whether it's required)."""

    field: str
    question: str


class JobOut(BaseModel):
    """Job representation returned to the client.

    `next_followup` is computed at request time (not persisted on the Job
    model) — see services/job_service.py's `_next_followup_prompt`. It is
    `None` once there's nothing safety-critical left to ask.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    description: str
    category: str
    skill_level: str | None = None
    urgency: str | None = None
    followup_answers: dict
    status: str
    created_at: datetime
    next_followup: FollowupPrompt | None = None


class AssessJobResponse(BaseModel):
    """POST /jobs/{id}/assess response — thin wrapper; full detail lives at
    GET /assessments/{job_id}."""

    job_id: UUID
    status: str
    risk_level: int | None = None
