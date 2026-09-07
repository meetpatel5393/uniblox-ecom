import uuid

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.models import Order
from app.repositories import order as order_repo
import math

from app.schemas.order import OrderItemResponse, OrderListResponse, OrderResponse


def list_all(db: Session, *, page: int = 1, page_size: int = 10) -> OrderListResponse:
    page = max(1, page)
    offset = (page - 1) * page_size
    total = order_repo.count_all(db)
    orders = order_repo.get_all(db, offset=offset, limit=page_size)
    return OrderListResponse(
        orders=[to_response(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


def get(db: Session, public_id: uuid.UUID) -> OrderResponse:
    order = order_repo.get_by_public_id(db, public_id)
    if not order:
        raise NotFoundError("Order not found")
    return to_response(order)


def to_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.public_id,
        status=order.status,
        gross_cents=order.gross_cents,
        discount_cents=order.discount_cents,
        net_cents=order.net_cents,
        currency=order.currency,
        coupon_code=order.coupon.code if order.coupon else None,
        items=[
            OrderItemResponse(
                product_name=item.product_name,
                price_cents=item.price_cents,
                qty=item.qty,
                subtotal_cents=item.subtotal_cents,
            )
            for item in order.items
        ],
        created_at=order.created_at,
    )
