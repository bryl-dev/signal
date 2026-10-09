import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.core.config import settings
from app.db.base import Base


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(120))
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.embedding_dim).with_variant(JSON, "sqlite")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
