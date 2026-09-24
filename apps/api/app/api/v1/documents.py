from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.db.session import get_db
from app.ingest.pipeline import ingest_all
from app.models.document import Document
from app.models.user import User
from app.schemas.documents import DocumentListResponse, DocumentResponse, IngestResponse

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=40, ge=1, le=100),
) -> DocumentListResponse:
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.source))
        .order_by(Document.ingested_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return DocumentListResponse(
        items=[
            DocumentResponse(
                id=row.id,
                title=row.title,
                url=row.url,
                source_name=row.source.name,
                source_type=row.source.source_type,
                author=row.author,
                published_at=row.published_at,
                ingested_at=row.ingested_at,
                content_type=row.content_type,
                excerpt=row.content_text[:240],
            )
            for row in rows
        ]
    )


@router.post("/ingest", response_model=IngestResponse)
async def run_ingest(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> IngestResponse:
    summary = await ingest_all(db)
    return IngestResponse(**summary)
