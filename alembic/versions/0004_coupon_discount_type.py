"""coupon_discount_type

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-08

Adds discount_type (percent/fixed) and discount_amount_cents columns to coupons.
Existing rows default to percent discount with no fixed amount.
Uses IF NOT EXISTS so the migration is idempotent against a live DB that
already had these columns applied outside of Alembic.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0004"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # Add discount_type only if it doesn't already exist
    conn.execute(text("""
        ALTER TABLE coupons
        ADD COLUMN IF NOT EXISTS discount_type VARCHAR(16) NOT NULL DEFAULT 'percent'
    """))
    # Add discount_amount_cents only if it doesn't already exist
    conn.execute(text("""
        ALTER TABLE coupons
        ADD COLUMN IF NOT EXISTS discount_amount_cents INTEGER NULL
    """))


def downgrade() -> None:
    op.drop_column("coupons", "discount_amount_cents")
    op.drop_column("coupons", "discount_type")

