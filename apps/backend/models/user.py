"""User model — srs.md §6.1 `users` table (minimum viable subset).

Only the fields needed for JWT auth are implemented. The full `users` entity
in srs.md also carries `role` (admin/professional) and contact fields — out
of scope here since this product has a single `user` role (CLAUDE.md,
architecture.md §1) and no professional/vendor accounts.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class User(Base):
    """A registered end user. Single role: `user` (no admin/professional)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    jobs: Mapped[list["Job"]] = relationship(back_populates="user")  # noqa: F821
