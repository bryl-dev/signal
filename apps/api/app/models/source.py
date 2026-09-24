import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.ingestion import IngestionRun


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    homepage_url: Mapped[str] = mapped_column(Text)
    fetch_config: Mapped[dict] = mapped_column(
        JSON().with_variant(SQLiteJSON, "sqlite"),
        default=lambda: {},
    )
    quality_tier: Mapped[str] = mapped_column(String(32), default="unknown")
    default_content_type: Mapped[str] = mapped_column(String(32), default="news")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="source")
    runs: Mapped[list["IngestionRun"]] = relationship(back_populates="source")
