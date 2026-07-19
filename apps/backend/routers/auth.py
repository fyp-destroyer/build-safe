"""Auth router — login/register. Real JWT auth via services/auth_service.py
and core/security.py."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user, token = await auth_service.register(db, payload)
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user, token = await auth_service.login(db, payload)
    return TokenResponse(access_token=token, user=user)
