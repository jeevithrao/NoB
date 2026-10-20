"""account fields: username, preferences, deletion marker, otp purpose

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=30), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])
    op.create_check_constraint("ck_users_username_format", "users", "username IS NULL OR username ~ '^[a-z0-9_]{3,30}$'")
    op.add_column("users", sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("users", sa.Column("analytics_opt_in", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("otp_requests", sa.Column("purpose", sa.String(length=20), server_default="login", nullable=False))


def downgrade() -> None:
    op.drop_column("otp_requests", "purpose")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "analytics_opt_in")
    op.drop_column("users", "notifications_enabled")
    op.drop_constraint("ck_users_username_format", "users", type_="check")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "username")
