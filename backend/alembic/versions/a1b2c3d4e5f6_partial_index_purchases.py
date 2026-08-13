"""Replace purchases UniqueConstraint with partial unique index

Allows purchase retries after a failed payment without hitting the
unique constraint. Only one pending or completed purchase per user-tour
pair is permitted; failed rows are excluded from the index.

Revision ID: a1b2c3d4e5f6
Revises: f748e6eddcee
Create Date: 2026-08-08
"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f748e6eddcee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old hard constraint that prevented any second row per user-tour
    op.drop_constraint('purchases_user_id_tour_id_key', 'purchases', type_='unique')
    # Replace with a partial unique index that only covers active purchases
    op.execute("""
        CREATE UNIQUE INDEX idx_one_active_purchase_per_user_tour
        ON purchases(user_id, tour_id)
        WHERE status IN ('pending', 'completed')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_one_active_purchase_per_user_tour")
    op.create_unique_constraint('purchases_user_id_tour_id_key', 'purchases', ['user_id', 'tour_id'])
