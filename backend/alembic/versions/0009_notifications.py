"""in-app notifications

Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subtitle", sa.Text(), nullable=True),
        sa.Column("tour_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dedupe_key", sa.String(length=120), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('reminder', 'confirmed', 'new', 'review')", name="ck_notifications_type"),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
