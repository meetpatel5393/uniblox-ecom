import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrderStatus:
    """SmallInteger constants — cheaper than string enums, extendable without schema change."""
    PLACED = 1


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # RFC 5321 defines 254 as the max valid email length
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="customer")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    # boolean (1 byte) — more efficient than storing status strings
    checked_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="carts")
    items: Mapped[list["CartItem"]] = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    order: Mapped["Order | None"] = relationship("Order", back_populates="cart", uselist=False)

    __table_args__ = (
        Index("ix_carts_customer_id", "customer_id"),
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carts.id"), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), primary_key=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_cart_item_qty_positive"),
    )


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 32 chars — sized for UUID hex without dashes
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    discount_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    min_order_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # milestone_n matches the README's n term — which nth order triggered this coupon
    milestone_n: Mapped[int] = mapped_column(Integer, nullable=False)
    # max number of customers that can redeem this coupon
    max_uses: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    generated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    redemptions: Mapped[list["CouponRedemption"]] = relationship("CouponRedemption", back_populates="coupon")

    __table_args__ = (
        CheckConstraint("discount_pct > 0 AND discount_pct <= 100", name="ck_coupon_discount_pct_valid"),
        CheckConstraint("min_order_cents >= 0", name="ck_coupon_min_order_non_negative"),
        CheckConstraint("max_uses > 0", name="ck_coupon_max_uses_positive"),
    )


class CouponRedemption(Base):
    """Tracks each use of a coupon — supports multi-use coupons (1 coupon : N redemptions)."""
    __tablename__ = "coupon_redemptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique on cart_id enforces one order per cart — acts as natural idempotency key
    cart_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("carts.id"), nullable=False, unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    # which coupon was applied — full redemption details in coupon_redemptions
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("coupons.id"), nullable=True)
    # SmallInteger (2 bytes) — use OrderStatus constants, extendable without schema change
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=OrderStatus.PLACED)
    gross_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # ISO 4217 currency codes are exactly 3 characters (e.g. USD, INR)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    cart: Mapped["Cart"] = relationship("Cart", back_populates="order")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    coupon: Mapped["Coupon | None"] = relationship("Coupon", foreign_keys=[coupon_id])
    coupon_redemption: Mapped["CouponRedemption | None"] = relationship("CouponRedemption", back_populates="order", uselist=False)
    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("gross_cents > 0", name="ck_order_gross_positive"),
        CheckConstraint("discount_cents >= 0", name="ck_order_discount_non_negative"),
        CheckConstraint("net_cents >= 0", name="ck_order_net_non_negative"),
        Index("ix_orders_customer_id", "customer_id"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
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
