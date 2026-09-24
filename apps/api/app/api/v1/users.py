from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _onboarded, _to_response
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserResponse

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserResponse)
async def read_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return _to_response(user, await _onboarded(db, user.id))
