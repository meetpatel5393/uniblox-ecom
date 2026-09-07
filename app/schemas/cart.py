import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CartCreate(BaseModel):
    customer_id: uuid.UUID


class CartItemAdd(BaseModel):
    product_id: uuid.UUID
    qty: int = Field(..., ge=1)


class CartItemUpdate(BaseModel):
    qty: int = Field(..., ge=1)


class CartItemResponse(BaseModel):
    product_id: uuid.UUID
    product_name: str
    price_cents: int
    qty: int
    subtotal_cents: int


class CartResponse(BaseModel):
    id: uuid.UUID
    checked_out: bool
    items: list[CartItemResponse]
    total_cents: int
    created_at: datetime


class CheckoutRequest(BaseModel):
    coupon_code: str | None = None
