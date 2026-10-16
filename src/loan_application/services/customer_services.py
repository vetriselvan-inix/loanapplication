from sqlalchemy.orm import Session

from loan_application.exceptions import (
    ConflictError,
    CustomerNotFound,
    InvalidInputError,
)
from loan_application.repositories import customer_repositories
from loan_application.schemas.customer_schemas import CustomerIn
from loan_application.services.transaction import transaction
from loan_application.tables import Customer

DUPLICATE_EMAIL = "Customer with this email already exists"


def get_customer(db, customer_id: int):
    if customer_id < 0:
        raise InvalidInputError("id must be a positive integer")
    customer = customer_repositories.get_by_id(db, customer_id)
    if customer is None:
        raise CustomerNotFound(customer_id)
    return customer


def add_customer(db: Session, data: CustomerIn) -> Customer:
    """Stage a new customer in the caller's transaction. Does not commit."""
    customer_data = data.model_dump()
    customer_data["email"] = data.email.strip().lower()

    if customer_repositories.email_exists(db, customer_data["email"]):
        raise ConflictError(DUPLICATE_EMAIL)

    customer = Customer(**customer_data)
    customer_repositories.add(db, customer)
    db.flush()  # send the INSERT so customer.id is available, still uncommitted
    return customer


def create_customer(db: Session, data: CustomerIn) -> Customer:
    with transaction(db, DUPLICATE_EMAIL):
        customer = add_customer(db, data)
    db.refresh(customer)
    return customer


def update_customer(db: Session, customer_id: int, data: CustomerIn) -> Customer:
    customer = get_customer(db, customer_id)

    if customer_repositories.email_taken_by_other(db, data.email, customer_id):
        raise ConflictError(DUPLICATE_EMAIL)

    with transaction(db, DUPLICATE_EMAIL):
        for key, value in data.model_dump().items():
            setattr(customer, key, value)
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: int) -> None:
    customer = get_customer(db, customer_id)
    with transaction(db, "Customer has loan records and cannot be deleted"):
        customer_repositories.delete(db, customer)
