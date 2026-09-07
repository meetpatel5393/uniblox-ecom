import uuid

from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.models import Product
from app.repositories import product as product_repo
from app.schemas.product import ProductResponse


def list_all(db: Session) -> list[ProductResponse]:
    return [_to_response(p) for p in product_repo.get_all(db)]


def get(db: Session, public_id: uuid.UUID) -> ProductResponse:
    product = product_repo.get_by_public_id(db, public_id)
    if not product:
        raise NotFoundError("Product not found")
    return _to_response(product)


def _to_response(product: Product) -> ProductResponse:
    return ProductResponse(
        id=product.public_id,
        name=product.name,
        price_cents=product.price_cents,
        stock_qty=product.stock_qty,
    )
