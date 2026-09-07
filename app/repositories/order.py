import uuid

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.models import Order, OrderItem


def _eager(query):
    return query.options(selectinload(Order.items), joinedload(Order.coupon))


def get_by_public_id(db: Session, public_id: uuid.UUID) -> Order | None:
    return _eager(db.query(Order)).filter(Order.public_id == public_id).first()


def get_by_cart_id(db: Session, cart_id: int) -> Order | None:
    """Idempotency lookup — returns the existing order if this cart was already checked out."""
    return _eager(db.query(Order)).filter(Order.cart_id == cart_id).first()


def get_all(db: Session, *, offset: int = 0, limit: int = 20) -> list[Order]:
    return (
        _eager(db.query(Order))
        .order_by(Order.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_all(db: Session) -> int:
    return db.query(Order).count()


def create(
    db: Session,
    *,
    cart_id: int,
    customer_id: int,
    coupon_id: int | None,
    gross_cents: int,
    discount_cents: int,
    net_cents: int,
    currency: str,
) -> Order:
    order = Order(
        cart_id=cart_id,
        customer_id=customer_id,
        coupon_id=coupon_id,
        gross_cents=gross_cents,
        discount_cents=discount_cents,
        net_cents=net_cents,
        currency=currency,
    )
    db.add(order)
    # flush to materialise order.id so FK references in order_items resolve within the transaction
    db.flush()
    return order


def add_item(
    db: Session,
    *,
    order_id: int,
    product_id: int,
    product_name: str,
    price_cents: int,
    qty: int,
    subtotal_cents: int,
) -> OrderItem:
    item = OrderItem(
        order_id=order_id,
        product_id=product_id,
        product_name=product_name,
        price_cents=price_cents,
        qty=qty,
        subtotal_cents=subtotal_cents,
    )
    db.add(item)
    return item
