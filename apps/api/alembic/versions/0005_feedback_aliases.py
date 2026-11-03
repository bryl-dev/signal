"""topic and interest aliases, story_feedback

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("topics", sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column(
        "user_interests", sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]")
    )
    op.create_table(
        "story_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column("topic_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "document_id", name="uq_feedback_user_doc"),
    )
    op.create_index(op.f("ix_story_feedback_user_id"), "story_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_story_feedback_user_id"), table_name="story_feedback")
    op.drop_table("story_feedback")
    op.drop_column("user_interests", "aliases")
    op.drop_column("topics", "aliases")
