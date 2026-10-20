"""purchases.device_rebound_at for the self-service device move

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("purchases", sa.Column("device_rebound_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("purchases", "device_rebound_at")
