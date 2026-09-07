import uuid

from sqlalchemy.orm import Session

from app.models.models import Product


def get_all(db: Session) -> list[Product]:
    return db.query(Product).order_by(Product.id).all()


def get_by_public_id(db: Session, public_id: uuid.UUID) -> Product | None:
    return db.query(Product).filter(Product.public_id == public_id).first()


def get_by_ids_for_update(db: Session, ids: list[int]) -> list[Product]:
    """Lock product rows in ascending id order — prevents deadlocks across concurrent checkouts."""
    return (
        db.query(Product)
        .filter(Product.id.in_(ids))
        .order_by(Product.id)
        .with_for_update()
        .all()
    )
