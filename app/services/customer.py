import uuid

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.models import Customer
from app.repositories import customer as customer_repo
from app.schemas.customer import CustomerCreate, CustomerResponse


def create(db: Session, payload: CustomerCreate) -> CustomerResponse:
    if customer_repo.get_by_email(db, payload.email):
        raise ConflictError(f"Email '{payload.email}' is already registered")
    customer = customer_repo.create(db, name=payload.name, email=payload.email)
    db.commit()
    db.refresh(customer)
    return _to_response(customer)


def list_all(db: Session) -> list[CustomerResponse]:
    return [_to_response(c) for c in customer_repo.get_all(db)]


def get(db: Session, public_id: uuid.UUID) -> CustomerResponse:
    customer = customer_repo.get_by_public_id(db, public_id)
    if not customer:
        raise NotFoundError("Customer not found")
    return _to_response(customer)


def _to_response(customer: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=customer.public_id,
        name=customer.name,
        email=customer.email,
        created_at=customer.created_at,
    )
