import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.exceptions import ConflictError, NotFoundError, UnprocessableError
from app.repositories import cart as cart_repo
from app.repositories import coupon as coupon_repo
from app.repositories import order as order_repo
from app.repositories import product as product_repo
from app.schemas.order import OrderResponse
from app.services.order import to_response


def checkout(
    db: Session,
    cart_public_id: uuid.UUID,
    coupon_code: str | None,
) -> OrderResponse:
    # 1. Lock cart row — serialises concurrent checkouts for the same cart
    cart = cart_repo.get_by_public_id_for_update(db, cart_public_id)
    if not cart:
        raise NotFoundError("Cart not found")

    # 2. Idempotency: already checked out → return existing order, no-op
    if cart.checked_out:
        existing = order_repo.get_by_cart_id(db, cart.id)
        if existing:
            return to_response(existing)

    # 3. Guard: empty cart
    if not cart.items:
        raise UnprocessableError("Cart is empty")

    # 4. Lock all products in ascending id order — consistent ordering prevents deadlocks
    #    when two concurrent carts share overlapping products
    product_ids = sorted(item.product_id for item in cart.items)
    products = product_repo.get_by_ids_for_update(db, product_ids)
    product_map = {p.id: p for p in products}

    # 5. Validate stock for every item before touching anything
    for cart_item in cart.items:
        product = product_map[cart_item.product_id]
        if product.stock_qty < cart_item.qty:
            raise UnprocessableError(
                f"Insufficient stock for '{product.name}': "
                f"{product.stock_qty} available, {cart_item.qty} requested"
            )

    # 6. Gross total using current product prices (snapshot happens in step 9)
    gross_cents = sum(
        product_map[ci.product_id].price_cents * ci.qty for ci in cart.items
    )

    # 7. Validate and lock coupon — FOR UPDATE prevents parallel exhaustion exploit
    discount_cents = 0
    coupon = None
    if coupon_code:
        coupon = coupon_repo.get_by_code_for_update(db, coupon_code)
        if not coupon:
            raise NotFoundError(f"Coupon '{coupon_code}' not found")
        if gross_cents < coupon.min_order_cents:
            min_dollars = coupon.min_order_cents / 100
            raise UnprocessableError(
                f"Minimum order total for this coupon is ${min_dollars:.2f} ({coupon.min_order_cents} cents)"
            )
        used = coupon_repo.count_redemptions(db, coupon.id)
        if used >= coupon.max_uses:
            raise ConflictError(f"Coupon '{coupon_code}' has been fully redeemed")
        
        if getattr(coupon, "discount_type", "percent") == "fixed" and coupon.discount_amount_cents:
            discount_cents = min(gross_cents, coupon.discount_amount_cents)
        else:
            discount_cents = (gross_cents * coupon.discount_pct) // 100

    net_cents = gross_cents - discount_cents

    # 8. Create the order record; flush to get order.id for FK references below
    order = order_repo.create(
        db,
        cart_id=cart.id,
        customer_id=cart.customer_id,
        coupon_id=coupon.id if coupon else None,
        gross_cents=gross_cents,
        discount_cents=discount_cents,
        net_cents=net_cents,
        currency=settings.currency,
    )

    # 9. Snapshot prices into order items + decrement stock
    #    We hold FOR UPDATE on every product row, so ORM decrement is atomically safe
    for cart_item in cart.items:
        product = product_map[cart_item.product_id]
        order_repo.add_item(
            db,
            order_id=order.id,
            product_id=product.id,
            product_name=product.name,       # snapshot — immune to future price changes
            price_cents=product.price_cents,  # snapshot
            qty=cart_item.qty,
            subtotal_cents=product.price_cents * cart_item.qty,
        )
        product.stock_qty -= cart_item.qty

    # 10. Record coupon redemption
    if coupon:
        coupon_repo.create_redemption(
            db,
            coupon_id=coupon.id,
            order_id=order.id,
            customer_id=cart.customer_id,
        )

    # 11. Seal the cart — subsequent checkout calls return the order above (step 2)
    cart_repo.mark_checked_out(db, cart)

    db.commit()

    # Reload with relationships for the response (commit expires ORM attributes)
    return to_response(order_repo.get_by_cart_id(db, cart.id))
