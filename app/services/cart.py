import uuid

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.models.models import Cart
from app.repositories import cart as cart_repo
from app.repositories import customer as customer_repo
from app.repositories import product as product_repo
from app.schemas.cart import CartItemResponse, CartResponse


def create(db: Session, customer_public_id: uuid.UUID) -> CartResponse:
    customer = customer_repo.get_by_public_id(db, customer_public_id)
    if not customer:
        raise NotFoundError("Customer not found")
    cart = cart_repo.create(db, customer_id=customer.id)
    db.commit()
    db.refresh(cart)
    return _to_response(cart)


def get(db: Session, cart_public_id: uuid.UUID) -> CartResponse:
    cart = cart_repo.get_by_public_id(db, cart_public_id)
    if not cart:
        raise NotFoundError("Cart not found")
    return _to_response(cart)


def add_item(
    db: Session,
    cart_public_id: uuid.UUID,
    product_public_id: uuid.UUID,
    qty: int,
) -> CartResponse:
    cart = cart_repo.get_by_public_id(db, cart_public_id)
    if not cart:
        raise NotFoundError("Cart not found")
    if cart.checked_out:
        raise ConflictError("Cart is already checked out")

    product = product_repo.get_by_public_id(db, product_public_id)
    if not product:
        raise NotFoundError("Product not found")
    if product.stock_qty < qty:
        raise UnprocessableError(
            f"Only {product.stock_qty} units of '{product.name}' available"
        )

    cart_repo.upsert_item(db, cart_id=cart.id, product_id=product.id, qty=qty)
    db.commit()
    return _to_response(cart_repo.get_by_public_id(db, cart_public_id))


def update_item(
    db: Session,
    cart_public_id: uuid.UUID,
    product_public_id: uuid.UUID,
    qty: int,
) -> CartResponse:
    cart = cart_repo.get_by_public_id(db, cart_public_id)
    if not cart:
        raise NotFoundError("Cart not found")
    if cart.checked_out:
        raise ConflictError("Cart is already checked out")

    product = product_repo.get_by_public_id(db, product_public_id)
    if not product:
        raise NotFoundError("Product not found")
    if product.stock_qty < qty:
        raise UnprocessableError(
            f"Only {product.stock_qty} units of '{product.name}' available"
        )

    item = cart_repo.set_item_qty(db, cart_id=cart.id, product_id=product.id, qty=qty)
    if not item:
        raise NotFoundError("Item not in cart — use POST /items to add it first")
    db.commit()
    return _to_response(cart_repo.get_by_public_id(db, cart_public_id))


def remove_item(
    db: Session,
    cart_public_id: uuid.UUID,
    product_public_id: uuid.UUID,
) -> CartResponse:
    cart = cart_repo.get_by_public_id(db, cart_public_id)
    if not cart:
        raise NotFoundError("Cart not found")
    if cart.checked_out:
        raise ConflictError("Cart is already checked out")

    product = product_repo.get_by_public_id(db, product_public_id)
    if not product:
        raise NotFoundError("Product not found")

    removed = cart_repo.remove_item(db, cart_id=cart.id, product_id=product.id)
    if not removed:
        raise NotFoundError("Item not in cart")
    db.commit()
    return _to_response(cart_repo.get_by_public_id(db, cart_public_id))


def _to_response(cart: Cart) -> CartResponse:
    items = [
        CartItemResponse(
            product_id=item.product.public_id,
            product_name=item.product.name,
            price_cents=item.product.price_cents,
            qty=item.qty,
            subtotal_cents=item.product.price_cents * item.qty,
        )
        for item in cart.items
    ]
    return CartResponse(
        id=cart.public_id,
        checked_out=cart.checked_out,
        items=items,
        total_cents=sum(i.subtotal_cents for i in items),
        created_at=cart.created_at,
    )
