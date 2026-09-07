import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.product import ProductResponse
from app.services import product as product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=list[ProductResponse],
    summary="List all products",
    description=(
        "Returns the full product catalog with current stock quantities. "
        "`price_cents` is an integer in the smallest currency unit (cents). "
        "Products with `stock_qty = 0` are out of stock and cannot be added to a cart."
    ),
    responses={
        200: {"description": "Array of products (may be empty)."},
    },
)
def list_products(db: Session = Depends(get_db)):
    return product_service.list_all(db)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get a single product",
    description="Retrieve one product by its public UUID.",
    responses={
        200: {"description": "Product record."},
        404: {"description": "Product not found."},
    },
)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)):
    return product_service.get(db, product_id)
