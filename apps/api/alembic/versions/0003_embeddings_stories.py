"""document_embeddings (pgvector), stories, story_members

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_embeddings",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )

    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("representative_document_id", sa.Uuid(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["representative_document_id"], ["documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stories_last_seen_at"), "stories", ["last_seen_at"], unique=False)

    op.create_table(
        "story_members",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
    )
    op.create_index(
        op.f("ix_story_members_story_id"), "story_members", ["story_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_story_members_story_id"), table_name="story_members")
    op.drop_table("story_members")
    op.drop_index(op.f("ix_stories_last_seen_at"), table_name="stories")
    op.drop_table("stories")
    op.drop_table("document_embeddings")
