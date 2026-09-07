import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.customer import CustomerCreate, CustomerResponse
from app.services import customer as customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get(
    "",
    response_model=list[CustomerResponse],
    summary="List all customers",
    description="Returns all registered customers, newest first.",
    responses={200: {"description": "Array of customers (may be empty)."}},
)
def list_customers(db: Session = Depends(get_db)):
    return customer_service.list_all(db)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    summary="Register a new customer",
    description=(
        "Creates a customer account with a name and email address. "
        "Email must be unique — attempting to register with an existing address returns **409**."
    ),
    responses={
        201: {"description": "Customer created successfully."},
        409: {"description": "A customer with this email already exists."},
        422: {"description": "Validation error — missing or malformed fields."},
    },
)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    return customer_service.create(db, payload)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Retrieve a customer",
    description="Fetch a customer by their public UUID. Returns **404** if not found.",
    responses={
        200: {"description": "Customer record."},
        404: {"description": "Customer not found."},
    },
)
def get_customer(customer_id: uuid.UUID, db: Session = Depends(get_db)):
    return customer_service.get(db, customer_id)
