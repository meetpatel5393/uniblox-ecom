import uuid

from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.models import Cart, CartItem


def _eager(query):
    """Eager-load items → products in two queries; avoids a cartesian-product JOIN."""
    return query.options(selectinload(Cart.items).joinedload(CartItem.product))


def create(db: Session, *, customer_id: int) -> Cart:
    cart = Cart(customer_id=customer_id)
    db.add(cart)
    db.flush()
    return cart


def get_by_public_id(db: Session, public_id: uuid.UUID) -> Cart | None:
    return _eager(db.query(Cart)).filter(Cart.public_id == public_id).first()


def get_by_public_id_for_update(db: Session, public_id: uuid.UUID) -> Cart | None:
    """Acquire row lock before checkout — prevents two concurrent checkouts of the same cart."""
    return (
        _eager(db.query(Cart))
        .filter(Cart.public_id == public_id)
        .with_for_update()
        .first()
    )


def get_item(db: Session, cart_id: int, product_id: int) -> CartItem | None:
    return (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
        .first()
    )


def upsert_item(db: Session, *, cart_id: int, product_id: int, qty: int) -> CartItem:
    """Increment qty if item exists; otherwise create it."""
    item = get_item(db, cart_id, product_id)
    if item:
        item.qty += qty
        return item
    item = CartItem(cart_id=cart_id, product_id=product_id, qty=qty)
    db.add(item)
    db.flush()
    return item


def set_item_qty(
    db: Session, *, cart_id: int, product_id: int, qty: int
) -> CartItem | None:
    item = get_item(db, cart_id, product_id)
    if item:
        item.qty = qty
    return item


def remove_item(db: Session, *, cart_id: int, product_id: int) -> bool:
    item = get_item(db, cart_id, product_id)
    if not item:
        return False
    db.delete(item)
    return True


def mark_checked_out(db: Session, cart: Cart) -> None:
    cart.checked_out = True
