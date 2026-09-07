import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.utils import uuid7


class OrderStatus:
    """SmallInteger constants — cheaper than string enums, extendable without schema change."""

    PLACED = 1


class Customer(Base):
    __tablename__ = "customers"

    # BIGINT PK for fast internal joins; public_id UUID exposed to callers
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid7
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # RFC 5321 defines 254 as the max valid email length
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="customer")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid7
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # stored as integer cents to eliminate float precision errors
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("price_cents > 0", name="ck_product_price_positive"),
        CheckConstraint("stock_qty >= 0", name="ck_product_stock_non_negative"),
    )


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid7
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id"), nullable=False
    )
    # boolean (1 byte) — more efficient than storing status strings
    checked_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )
    order: Mapped["Order | None"] = relationship(
        "Order", back_populates="cart", uselist=False
    )

    __table_args__ = (Index("ix_carts_customer_id", "customer_id"),)


class CartItem(Base):
    """High-volume join table — no public_id needed, never exposed in URLs."""

    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("carts.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False
    )
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        # unique constraint replaces the old composite PK — same invariant, BIGINT PK is faster
        UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),
        CheckConstraint("qty > 0", name="ck_cart_item_qty_positive"),
    )


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid7
    )
    # 32 chars — sized for UUID hex without dashes
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    discount_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    discount_type: Mapped[str] = mapped_column(String(16), nullable=False, default="percent")
    discount_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    min_order_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # milestone_n matches the README's n term — which nth-order milestone generated this coupon
    milestone_n: Mapped[int] = mapped_column(Integer, nullable=False)
    # max number of customers that can redeem this coupon
    max_uses: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption", back_populates="coupon"
    )

    __table_args__ = (
        CheckConstraint(
            "discount_pct >= 0 AND discount_pct <= 100", name="ck_coupon_discount_pct_valid"
        ),
        CheckConstraint("min_order_cents >= 0", name="ck_coupon_min_order_non_negative"),
        CheckConstraint("max_uses > 0", name="ck_coupon_max_uses_positive"),
        # No unique constraint on milestone_n — admin creates multiple coupons per milestone as a pool
    )


class CouponRedemption(Base):
    """Tracks each use of a coupon — supports multi-use coupons (1 coupon : N redemptions).

    High-volume join table — no public_id needed.
    """

    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("coupons.id"), nullable=False
    )
    # unique per order — one discount per checkout, enforced at DB level
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False, unique=True
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id"), nullable=False
    )
    redeemed_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    coupon: Mapped["Coupon"] = relationship("Coupon", back_populates="redemptions")
    order: Mapped["Order"] = relationship("Order", back_populates="coupon_redemption")
    customer: Mapped["Customer"] = relationship("Customer")

    __table_args__ = (
        Index("ix_coupon_redemptions_coupon_id", "coupon_id"),
        Index("ix_coupon_redemptions_customer_id", "customer_id"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, default=uuid7
    )
    # unique on cart_id enforces one order per cart — natural idempotency, no client key needed
    cart_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carts.id"), nullable=False, unique=True
    )
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("customers.id"), nullable=False
    )
    # which coupon was applied — full redemption details in coupon_redemptions
    coupon_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("coupons.id"), nullable=True
    )
    # SmallInteger (2 bytes) — use OrderStatus constants, extendable without schema change
    status: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=OrderStatus.PLACED
    )
    gross_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # ISO 4217 currency codes are exactly 3 characters (e.g. USD, INR)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="order")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    coupon: Mapped["Coupon | None"] = relationship("Coupon", foreign_keys=[coupon_id])
    coupon_redemption: Mapped["CouponRedemption | None"] = relationship(
        "CouponRedemption", back_populates="order", uselist=False
    )
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("gross_cents > 0", name="ck_order_gross_positive"),
        CheckConstraint("discount_cents >= 0", name="ck_order_discount_non_negative"),
        CheckConstraint("net_cents >= 0", name="ck_order_net_non_negative"),
        Index("ix_orders_customer_id", "customer_id"),
    )


class OrderItem(Base):
    """High-volume snapshot table — no public_id needed, queried only via order_id."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False
    )
    # snapshotted at checkout — order history stays accurate even if product changes
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_order_item_qty_positive"),
        CheckConstraint("price_cents > 0", name="ck_order_item_price_positive"),
        CheckConstraint("subtotal_cents >= 0", name="ck_order_item_subtotal_non_negative"),
        Index("ix_order_items_order_id", "order_id"),
    )
