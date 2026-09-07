import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.order import OrderListResponse, OrderResponse
from app.services import order as order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List all orders",
    description="Returns all orders newest-first, paginated. Use `page` and `page_size` query params.",
    responses={200: {"description": "Paginated list of orders."}},
)
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return order_service.list_all(db, page=page, page_size=page_size)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Retrieve an order",
    description=(
        "Returns a placed order by its public UUID, including all line items "
        "(with price snapshots captured at checkout time), gross amount, discount, "
        "net total, and the coupon code used (if any).  \n\n"
        "Price snapshots are immutable — they reflect what the customer paid, "
        "regardless of subsequent product price changes."
    ),
    responses={
        200: {"description": "Order with items and discount breakdown."},
        404: {"description": "Order not found."},
    },
)
def get_order(order_id: uuid.UUID, db: Session = Depends(get_db)):
    return order_service.get(db, order_id)
