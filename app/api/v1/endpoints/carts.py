import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.cart import (
    CartCreate,
    CartItemAdd,
    CartItemUpdate,
    CartResponse,
    CheckoutRequest,
)
from app.schemas.order import OrderResponse
from app.services import cart as cart_service
from app.services import checkout as checkout_service

router = APIRouter(prefix="/carts", tags=["Carts"])


@router.post(
    "",
    response_model=CartResponse,
    status_code=201,
    summary="Create a cart",
    description=(
        "Creates an empty shopping cart for a customer. "
        "A customer may own multiple open carts simultaneously."
    ),
    responses={
        201: {"description": "Empty cart created."},
        404: {"description": "Customer not found."},
    },
)
def create_cart(payload: CartCreate, db: Session = Depends(get_db)):
    return cart_service.create(db, payload.customer_id)


@router.get(
    "/{cart_id}",
    response_model=CartResponse,
    summary="Retrieve a cart",
    description=(
        "Returns the cart with all line items, per-item subtotals, and the cart total. "
        "`checked_out: true` means the cart has been converted to an order."
    ),
    responses={
        200: {"description": "Cart with items and totals."},
        404: {"description": "Cart not found."},
    },
)
def get_cart(cart_id: uuid.UUID, db: Session = Depends(get_db)):
    return cart_service.get(db, cart_id)


@router.post(
    "/{cart_id}/items",
    response_model=CartResponse,
    status_code=201,
    summary="Add or increment a cart item",
    description=(
        "Adds a product to the cart. If the product is already in the cart, "
        "`qty` is **added** to the existing quantity (upsert). "
        "Returns **409** if the cart is already checked out. "
        "Returns **422** if requested qty exceeds available stock."
    ),
    responses={
        201: {"description": "Updated cart."},
        404: {"description": "Cart or product not found."},
        409: {"description": "Cart is already checked out."},
        422: {"description": "Requested quantity exceeds available stock, or qty < 1."},
    },
)
def add_item(cart_id: uuid.UUID, payload: CartItemAdd, db: Session = Depends(get_db)):
    return cart_service.add_item(db, cart_id, payload.product_id, payload.qty)


@router.patch(
    "/{cart_id}/items/{product_id}",
    response_model=CartResponse,
    summary="Update item quantity",
    description=(
        "Sets the quantity of a specific line item to the given value. "
        "Use `DELETE` instead to remove an item entirely. "
        "Returns **422** if qty exceeds available stock."
    ),
    responses={
        200: {"description": "Updated cart."},
        404: {"description": "Cart or product not in cart."},
        409: {"description": "Cart is already checked out."},
        422: {"description": "Requested quantity exceeds available stock, or qty < 1."},
    },
)
def update_item(
    cart_id: uuid.UUID,
    product_id: uuid.UUID,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
):
    return cart_service.update_item(db, cart_id, product_id, payload.qty)


@router.delete(
    "/{cart_id}/items/{product_id}",
    response_model=CartResponse,
    summary="Remove an item from the cart",
    description="Removes the specified product from the cart entirely.",
    responses={
        200: {"description": "Updated cart."},
        404: {"description": "Cart or product not in cart."},
        409: {"description": "Cart is already checked out."},
    },
)
def remove_item(
    cart_id: uuid.UUID,
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return cart_service.remove_item(db, cart_id, product_id)


@router.post(
    "/{cart_id}/checkout",
    response_model=OrderResponse,
    status_code=201,
    summary="Check out a cart",
    description=(
        "Converts the cart into an order. Atomically validates stock, applies an optional coupon "
        "discount, decrements inventory, and marks the cart as checked out.  \n\n"
        "**Idempotent:** submitting the same cart a second time (e.g. after a network timeout) "
        "returns the existing order without creating a duplicate or double-charging stock.  \n\n"
        "**Coupon rules:** the coupon code must exist, have remaining uses, and the order gross "
        "must meet the coupon's `min_order_cents` threshold. The discount is applied as "
        "`floor(gross * discount_pct / 100)`.  \n\n"
        "**Concurrency:** products are locked in ascending-id order inside a transaction "
        "to prevent oversell and deadlocks under concurrent checkout."
    ),
    responses={
        201: {"description": "Order placed. Returns the full order with discount breakdown."},
        404: {"description": "Cart not found, or coupon code not found."},
        409: {"description": "Cart is empty."},
        422: {
            "description": (
                "A product is out of stock, or coupon minimum order amount not met, "
                "or coupon has no remaining uses."
            )
        },
    },
)
def checkout(
    cart_id: uuid.UUID,
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
):
    return checkout_service.checkout(db, cart_id, payload.coupon_code)
