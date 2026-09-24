import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter, client_ip
from app.core.security import (
    clear_auth_cookies,
    decode_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.db.session import get_db
from app.models.interest import UserInterest
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])
_limiter = SlidingWindowLimiter(
    max_calls=settings.login_rate_limit,
    window_seconds=settings.login_rate_window_seconds,
)


async def _onboarded(db: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(func.count())
        .select_from(UserInterest)
        .where(UserInterest.user_id == user_id, UserInterest.is_muted.is_(False))
    )
    return int(result.scalar_one()) >= settings.min_interests


def _to_response(user: User, onboarded: bool) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        onboarded=onboarded,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    _limiter.check(f"register:{client_ip(request)}")
    email = payload.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password), settings={})
    db.add(user)
    await db.commit()
    await db.refresh(user)
    set_auth_cookies(response, str(user.id))
    return _to_response(user, onboarded=False)


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    _limiter.check(f"login:{client_ip(request)}")
    email = payload.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    set_auth_cookies(response, str(user.id))
    return _to_response(user, await _onboarded(db, user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_auth_cookies(response)


@router.post("/refresh", response_model=UserResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(token, "refresh")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

    set_auth_cookies(response, str(user.id))
    return _to_response(user, await _onboarded(db, user.id))
