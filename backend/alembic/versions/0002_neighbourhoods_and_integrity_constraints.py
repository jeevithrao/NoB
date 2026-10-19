"""neighbourhoods and integrity constraints

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19 04:50:16.657770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CHECKS = [
    ("users", "ck_users_role", "role IN ('user', 'admin')"),
    ("tours", "ck_tours_price_non_negative", "price_paise >= 0"),
    ("stops", "ck_stops_trigger_radius_positive", "trigger_radius_m > 0"),
    ("purchases", "ck_purchases_status", "status IN ('pending', 'completed', 'failed', 'refunded')"),
    ("purchases", "ck_purchases_amount_non_negative", "amount_paise >= 0"),
    ("tour_sessions", "ck_tour_sessions_stops_visited_non_negative", "stops_visited >= 0"),
    ("session_events", "ck_session_events_event_type", "event_type IN ('arrived', 'audio_started', 'audio_finished', 'skipped')"),
    ("tour_comments", "ck_tour_comments_content_length", "char_length(content) BETWEEN 1 AND 1000"),
]


def upgrade() -> None:
    op.create_table('neighbourhoods',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('cover_image', sa.String(length=500), nullable=True),
    sa.Column('centroid_lat', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('centroid_lng', sa.Numeric(precision=10, scale=7), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'city', name='uq_neighbourhoods_name_city'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('idx_tour_comments_tour_created', 'tour_comments', ['tour_id', 'created_at'], unique=False)
    op.create_index('idx_one_completed_session_per_user_tour', 'tour_sessions', ['user_id', 'tour_id'], unique=True, postgresql_where='completed = true')
    op.add_column('tours', sa.Column('neighbourhood_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_tours_neighbourhood_id'), 'tours', ['neighbourhood_id'], unique=False)
    op.create_foreign_key('fk_tours_neighbourhood_id', 'tours', 'neighbourhoods', ['neighbourhood_id'], ['id'], ondelete='SET NULL')

    # Integrity constraints (Alembic does not autogenerate CHECKs).
    for table, name, expr in CHECKS:
        op.create_check_constraint(name, table, expr)


def downgrade() -> None:
    for table, name, _expr in reversed(CHECKS):
        op.drop_constraint(name, table, type_='check')
    op.drop_constraint('fk_tours_neighbourhood_id', 'tours', type_='foreignkey')
    op.drop_index(op.f('ix_tours_neighbourhood_id'), table_name='tours')
    op.drop_column('tours', 'neighbourhood_id')
    op.drop_index('idx_one_completed_session_per_user_tour', table_name='tour_sessions', postgresql_where='completed = true')
    op.drop_index('idx_tour_comments_tour_created', table_name='tour_comments')
    op.drop_table('neighbourhoods')
