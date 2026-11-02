from sqlalchemy.orm import Session

from loan_application.exceptions import (
    ConflictError,
    CustomerNotFound,
    InvalidInputError,
)
from loan_application.repositories import customer_repositories
from loan_application.schemas.customer_schemas import CustomerIn, CustomerOut
from loan_application.services import credit_score
from loan_application.services.transaction import transaction
from loan_application.tables import Customer

DUPLICATE_EMAIL = "Customer with this email already exists"
DUPLICATE_PHONE = "Customer with this phone number already exists"
# For a database refusal the checks above did not foresee: it must not blame the email
SAVE_CONFLICT = "The customer could not be saved: the data conflicts with an existing record"


def get_customer(db, customer_id: int):
    if customer_id < 0:
        raise InvalidInputError("id must be a positive integer")
    customer = customer_repositories.get_by_id(db, customer_id)
    if customer is None:
        raise CustomerNotFound(customer_id)
    return customer


def get_customer_with_current_score(db: Session, customer_id: int) -> CustomerOut:
    """The customer as the API shows it, with the score worked out now instead of the
    stored one, which can lag (for example after a birthday). Changes nothing."""
    customer = get_customer(db, customer_id)
    shown = CustomerOut.model_validate(customer)
    shown.credit_score = credit_score.current_score(db, customer)
    return shown


def get_credit_score_breakdown(db: Session, customer_id: int) -> dict:
    """Where the customer's current credit score comes from. Changes nothing."""
    customer = get_customer(db, customer_id)
    return {"customer_id": customer.id, **credit_score.current_breakdown(db, customer)}


def add_customer(db: Session, data: CustomerIn) -> Customer:
    """Stage a new customer in the caller's transaction. Does not commit."""
    customer_data = data.model_dump()
    customer_data["email"] = data.email.strip().lower()

    if customer_repositories.email_exists(db, customer_data["email"]):
        raise ConflictError(DUPLICATE_EMAIL)
    if customer_repositories.phone_exists(db, customer_data["phone"]):
        raise ConflictError(DUPLICATE_PHONE)

    customer = Customer(**customer_data)
    credit_score.refresh_credit_score(db, customer)  # no loans yet
    customer_repositories.add(db, customer)
    db.flush()  # send the INSERT so customer.id is available, still uncommitted
    return customer


def create_customer(db: Session, data: CustomerIn) -> Customer:
    with transaction(db, SAVE_CONFLICT):
        customer = add_customer(db, data)
    db.refresh(customer)
    return customer


def update_customer(db: Session, customer_id: int, data: CustomerIn) -> Customer:
    customer = get_customer(db, customer_id)

    if customer_repositories.email_taken_by_other(db, data.email, customer_id):
        raise ConflictError(DUPLICATE_EMAIL)
    if customer_repositories.phone_taken_by_other(db, data.phone, customer_id):
        raise ConflictError(DUPLICATE_PHONE)

    with transaction(db, SAVE_CONFLICT):
        for key, value in data.model_dump().items():
            setattr(customer, key, value)
        # Income or date of birth may have changed
        credit_score.refresh_credit_score(db, customer)
    db.refresh(customer)
    return customer


def delete_customer(db: Session, customer_id: int) -> None:
    customer = get_customer(db, customer_id)
    with transaction(db, "Customer has loan records and cannot be deleted"):
        customer_repositories.delete(db, customer)
