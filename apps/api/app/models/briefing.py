import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base

_JSON = JSON().with_variant(SQLiteJSON, "sqlite")


class StorySummary(Base):
    """Cached LLM summary of a story. Invalid once the story's member set changes."""

    __tablename__ = "story_summaries"

    story_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    members_key: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(120))
    headline: Mapped[str] = mapped_column(String(300))
    bullets: Mapped[list] = mapped_column(_JSON)
    source_document_ids: Mapped[list] = mapped_column(_JSON)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(120))
    llm_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )


class BriefItem(Base):
    """A snapshot, so past briefs still render after stories are regrouped or pruned."""

    __tablename__ = "brief_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    brief_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("briefs.id", ondelete="CASCADE"), index=True
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stories.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(_JSON)
    headline: Mapped[str] = mapped_column(String(300))
    bullets: Mapped[list] = mapped_column(_JSON)
    # "llm" or "extractive"
    method: Mapped[str] = mapped_column(String(16))
    sources: Mapped[list] = mapped_column(_JSON)
