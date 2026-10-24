"""shared rate-limit counters

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("window_start", sa.BigInteger(), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start"),
    )
    op.create_index("ix_rate_limit_hits_window", "rate_limit_hits", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_hits_window", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
