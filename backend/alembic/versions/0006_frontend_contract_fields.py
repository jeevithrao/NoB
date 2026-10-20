"""frontend contract fields: tour presentation, stop teasers, neighbourhood tagline, booking ref, consent

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tours", sa.Column("preview_audio_title", sa.String(length=255), nullable=True))
    op.add_column("tours", sa.Column("theme", sa.String(length=50), nullable=True))
    op.add_column("tours", sa.Column("difficulty", sa.String(length=20), nullable=True))
    op.add_column("tours", sa.Column("start_point", sa.String(length=255), nullable=True))
    op.add_column(
        "tours",
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.create_index(op.f("ix_tours_theme"), "tours", ["theme"], unique=False)

    op.add_column("stops", sa.Column("blurb", sa.String(length=255), nullable=True))
    op.add_column("stops", sa.Column("icon", sa.String(length=16), nullable=True))

    op.add_column("neighbourhoods", sa.Column("tagline", sa.String(length=255), nullable=True))
    op.add_column("neighbourhoods", sa.Column("emoji", sa.String(length=16), nullable=True))

    # booking_ref: add nullable, backfill existing rows, then make it required + unique.
    op.add_column("purchases", sa.Column("booking_ref", sa.String(length=20), nullable=True))
    op.execute("UPDATE purchases SET booking_ref = 'NOB-' || upper(substr(md5(id::text), 1, 8))")
    op.alter_column(
        "purchases",
        "booking_ref",
        nullable=False,
        server_default=sa.text("'NOB-' || upper(substr(md5(random()::text || clock_timestamp()::text), 1, 8))"),
    )
    op.create_unique_constraint("uq_purchases_booking_ref", "purchases", ["booking_ref"])

    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("marketing_opt_in", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.create_check_constraint(
        "ck_tours_difficulty", "tours", "difficulty IS NULL OR difficulty IN ('Easy', 'Moderate', 'Hard')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_tours_difficulty", "tours", type_="check")
    op.drop_column("users", "marketing_opt_in")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
    op.drop_constraint("uq_purchases_booking_ref", "purchases", type_="unique")
    op.drop_column("purchases", "booking_ref")
    op.drop_column("neighbourhoods", "emoji")
    op.drop_column("neighbourhoods", "tagline")
    op.drop_column("stops", "icon")
    op.drop_column("stops", "blurb")
    op.drop_index(op.f("ix_tours_theme"), table_name="tours")
    op.drop_column("tours", "tags")
    op.drop_column("tours", "start_point")
    op.drop_column("tours", "difficulty")
    op.drop_column("tours", "theme")
    op.drop_column("tours", "preview_audio_title")
