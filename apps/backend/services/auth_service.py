"""Auth orchestration: register (hash + create user) and login (verify +
issue token)."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ApiError
from core.security import create_access_token, hash_password, verify_password
from models import User
from schemas.auth import LoginRequest, RegisterRequest


async def register(db: AsyncSession, payload: RegisterRequest) -> tuple[User, str]:
    """Create a new user. Raises ApiError(409) on duplicate email."""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise ApiError(
            409, "email_already_registered", "An account with this email already exists."
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ApiError(
            409, "email_already_registered", "An account with this email already exists."
        ) from None

    await db.refresh(user)
    token = create_access_token(str(user.id))
    return user, token


async def login(db: AsyncSession, payload: LoginRequest) -> tuple[User, str]:
    """Verify credentials and issue a token. Raises ApiError(401) on failure."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")

    token = create_access_token(str(user.id))
    return user, token
