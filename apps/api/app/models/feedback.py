import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.db.base import Base


class StoryFeedback(Base):
    """A thumbs up (+1) or down (-1) on a story.

    Keyed by the story's lead document rather than the story, because stories are rebuilt
    whenever grouping rules change and documents are not.
    """

    __tablename__ = "story_feedback"
    __table_args__ = (UniqueConstraint("user_id", "document_id", name="uq_feedback_user_doc"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE")
    )
    value: Mapped[int] = mapped_column(SmallInteger)
    # Topics the story matched when voted on; they drive the per-topic weight adjustment.
    topic_ids: Mapped[list] = mapped_column(JSON().with_variant(SQLiteJSON, "sqlite"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
