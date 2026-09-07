import uuid
from datetime import datetime

from pydantic import BaseModel


class OrderItemResponse(BaseModel):
    product_name: str
    price_cents: int
    qty: int
    subtotal_cents: int


class OrderResponse(BaseModel):
    id: uuid.UUID
    status: int
    gross_cents: int
    discount_cents: int
    net_cents: int
    currency: str
    coupon_code: str | None
    items: list[OrderItemResponse]
    created_at: datetime


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
