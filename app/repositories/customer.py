import uuid

from sqlalchemy.orm import Session

from app.models.models import Customer


def get_all(db: Session) -> list[Customer]:
    return db.query(Customer).order_by(Customer.created_at.desc()).all()


def get_by_public_id(db: Session, public_id: uuid.UUID) -> Customer | None:
    return db.query(Customer).filter(Customer.public_id == public_id).first()


def get_by_email(db: Session, email: str) -> Customer | None:
    return db.query(Customer).filter(Customer.email == email).first()


def create(db: Session, *, name: str, email: str) -> Customer:
    customer = Customer(name=name, email=email)
    db.add(customer)
    db.flush()
    return customer
