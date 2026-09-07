"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("stock_qty", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("price_cents > 0", name="ck_product_price_positive"),
        sa.CheckConstraint("stock_qty >= 0", name="ck_product_stock_non_negative"),
    )

    op.create_table(
        "coupons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("discount_pct", sa.SmallInteger(), nullable=False),
        sa.Column("min_order_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("milestone_n", sa.Integer(), nullable=False),
        sa.Column("max_uses", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        sa.CheckConstraint("discount_pct > 0 AND discount_pct <= 100", name="ck_coupon_discount_pct_valid"),
        sa.CheckConstraint("min_order_cents >= 0", name="ck_coupon_min_order_non_negative"),
        sa.CheckConstraint("max_uses > 0", name="ck_coupon_max_uses_positive"),
    )

    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("checked_out", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_carts_customer_id", "carts", ["customer_id"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coupons.id"), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("net_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("cart_id", name="uq_orders_cart_id"),
        sa.CheckConstraint("gross_cents > 0", name="ck_order_gross_positive"),
        sa.CheckConstraint("discount_cents >= 0", name="ck_order_discount_non_negative"),
        sa.CheckConstraint("net_cents >= 0", name="ck_order_net_non_negative"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),
    )
    op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"])
    op.create_index("ix_coupon_redemptions_customer_id", "coupon_redemptions", ["customer_id"])

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_order_item_qty_positive"),
        sa.CheckConstraint("price_cents > 0", name="ck_order_item_price_positive"),
        sa.CheckConstraint("subtotal_cents >= 0", name="ck_order_item_subtotal_non_negative"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    op.create_table(
        "cart_items",
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("carts.id"), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_cart_item_qty_positive"),
    )


def downgrade() -> None:
    op.drop_table("cart_items")
    op.drop_index("ix_order_items_order_id", "order_items")
    op.drop_table("order_items")
    op.drop_index("ix_coupon_redemptions_customer_id", "coupon_redemptions")
    op.drop_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions")
    op.drop_table("coupon_redemptions")
    op.drop_index("ix_orders_customer_id", "orders")
    op.drop_table("orders")
    op.drop_index("ix_carts_customer_id", "carts")
    op.drop_table("carts")
    op.drop_table("coupons")
    op.drop_table("products")
    op.drop_table("customers")
