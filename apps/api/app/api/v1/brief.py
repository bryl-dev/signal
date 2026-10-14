import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.briefing.llm import LLMClient, get_llm_client
from app.briefing.service import generate_brief, latest_brief
from app.clustering.embedder import get_embedder
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.briefing import Brief, BriefItem
from app.models.user import User
from app.schemas.brief import BriefEnvelope, BriefItemResponse, BriefResponse

router = APIRouter(tags=["brief"])


def _to_response(brief: Brief, items: list[BriefItem]) -> BriefResponse:
    return BriefResponse(
        id=brief.id,
        created_at=brief.created_at,
        model=brief.model,
        llm_error=brief.llm_error,
        items=[
            BriefItemResponse(
                story_id=item.story_id,
                position=item.position,
                score=item.score,
                reasons=item.reasons,
                headline=item.headline,
                bullets=item.bullets,
                method=item.method,
                sources=item.sources,
            )
            for item in items
        ],
    )


@router.get("/brief", response_model=BriefEnvelope)
async def get_latest_brief(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BriefEnvelope:
    found = await latest_brief(db, user.id)
    return BriefEnvelope(brief=_to_response(*found) if found else None)


@router.post("/brief", response_model=BriefResponse)
async def create_brief(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> BriefResponse:
    embedder = await asyncio.to_thread(get_embedder)
    brief, items = await generate_brief(db, user.id, llm, embedder)
    await db.refresh(brief)
    return _to_response(brief, items)
