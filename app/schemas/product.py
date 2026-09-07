import uuid

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    price_cents: int
    stock_qty: int
