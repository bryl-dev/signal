"""story_summaries, briefs, brief_items

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_summaries",
        sa.Column("story_id", sa.Uuid(), nullable=False),
        sa.Column("members_key", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("headline", sa.String(length=300), nullable=False),
        sa.Column("bullets", sa.JSON(), nullable=False),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("story_id"),
    )

    op.create_table(
        "briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("llm_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_briefs_user_id"), "briefs", ["user_id"], unique=False)
    op.create_index(op.f("ix_briefs_created_at"), "briefs", ["created_at"], unique=False)

    op.create_table(
        "brief_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("brief_id", sa.Uuid(), nullable=False),
        sa.Column("story_id", sa.Uuid(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("headline", sa.String(length=300), nullable=False),
        sa.Column("bullets", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["brief_id"], ["briefs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_brief_items_brief_id"), "brief_items", ["brief_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_brief_items_brief_id"), table_name="brief_items")
    op.drop_table("brief_items")
    op.drop_index(op.f("ix_briefs_created_at"), table_name="briefs")
    op.drop_index(op.f("ix_briefs_user_id"), table_name="briefs")
    op.drop_table("briefs")
    op.drop_table("story_summaries")
