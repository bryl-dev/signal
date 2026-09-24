from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.slugs import slugify
from app.db.session import get_db
from app.models.interest import UserInterest
from app.models.topic import Topic
from app.models.user import User
from app.schemas.interest import (
    CreateTopicRequest,
    InterestItem,
    InterestsResponse,
    TopicCatalogResponse,
    TopicCategoryResponse,
    TopicResponse,
    UpdateInterestsRequest,
)

router = APIRouter(tags=["interests"])

CATEGORY_LABELS = {
    "ai": "AI",
    "gaming": "Gaming",
    "anime": "Anime / Manga",
}


def _is_onboarded(count: int) -> bool:
    return count >= settings.min_interests


@router.get("/topics", response_model=TopicCatalogResponse)
async def list_topics(db: AsyncSession = Depends(get_db)) -> TopicCatalogResponse:
    result = await db.execute(select(Topic).order_by(Topic.category, Topic.sort_order, Topic.name))
    topics = result.scalars().all()
    grouped: dict[str, list[Topic]] = {}
    for topic in topics:
        grouped.setdefault(topic.category, []).append(topic)

    categories = []
    for category_id, label in CATEGORY_LABELS.items():
        items = grouped.get(category_id, [])
        categories.append(
            TopicCategoryResponse(
                id=category_id,
                name=label,
                topics=[_topic_response(topic) for topic in items],
            )
        )
    return TopicCatalogResponse(categories=categories)


def _topic_response(topic: Topic) -> TopicResponse:
    return TopicResponse(
        id=topic.id,
        slug=topic.slug,
        name=topic.name,
        category=topic.category,
        description=topic.description,
    )


@router.post("/topics", response_model=TopicResponse)
async def create_topic(
    payload: CreateTopicRequest,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TopicResponse:
    name = " ".join(payload.name.split())
    slug = slugify(name)
    if not slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Use letters or numbers in the topic name.",
        )

    existing = await db.execute(select(Topic).where(Topic.slug == slug))
    topic = existing.scalar_one_or_none()
    if topic is not None:
        return _topic_response(topic)

    topic = Topic(
        slug=slug,
        name=name,
        category=payload.category,
        description=None,
        sort_order=1000,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return _topic_response(topic)


@router.get("/me/interests", response_model=InterestsResponse)
async def get_interests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterestsResponse:
    result = await db.execute(
        select(UserInterest)
        .options(selectinload(UserInterest.topic))
        .where(UserInterest.user_id == user.id)
    )
    rows = result.scalars().all()
    items = [
        InterestItem(
            topic_id=row.topic_id,
            slug=row.topic.slug,
            name=row.topic.name,
            category=row.topic.category,
            weight=row.weight,
            is_muted=row.is_muted,
            source=row.source,
        )
        for row in rows
    ]
    return InterestsResponse(items=items, onboarded=_is_onboarded(len(items)))


@router.put("/me/interests", response_model=InterestsResponse)
async def replace_interests(
    payload: UpdateInterestsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InterestsResponse:
    unique_ids = list(dict.fromkeys(payload.topic_ids))
    if len(unique_ids) < settings.min_interests:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Select at least {settings.min_interests} interests.",
        )

    found = await db.execute(select(Topic).where(Topic.id.in_(unique_ids)))
    topics = found.scalars().all()
    if len(topics) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown topic id")

    await db.execute(delete(UserInterest).where(UserInterest.user_id == user.id))
    now = datetime.now(UTC)
    for topic in topics:
        db.add(
            UserInterest(
                user_id=user.id,
                topic_id=topic.id,
                weight=0.7,
                is_muted=False,
                source="explicit",
                created_at=now,
                updated_at=now,
            )
        )
    await db.commit()
    return await get_interests(user=user, db=db)
