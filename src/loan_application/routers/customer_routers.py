from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from loan_application.db import get_db
from loan_application.dependencies.auth import (
    authenticated_user,
    get_current_user,
    require_roles,
)
from loan_application.exceptions import InvalidInputError
from loan_application.schemas.customer_schemas import (
    CreditScoreOut,
    CustomerIn,
    CustomerOut,
    CustomerSummaryOut,
    EligibilityOut,
    MessageOut,
)
from loan_application.schemas.loan_schemas import LoanOut
from loan_application.services import (
    customer_services,
    eligibility_advice,
    loan_services,
)
from loan_application.services.access import ensure_can_access_customer
from loan_application.tables import User, UserRole

router = APIRouter(prefix="/customers", tags=["Customers"],  dependencies=[Depends(authenticated_user)],)
officer_only = [Depends(require_roles(UserRole.OFFICER))]


@router.post("/", response_model=CustomerOut, status_code=201,dependencies=officer_only)
def add_customer(data: CustomerIn, db: Session = Depends(get_db)):
    return customer_services.create_customer(db, data)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db),user: User = Depends(get_current_user),):
    ensure_can_access_customer(user, customer_id)
    return customer_services.get_customer_with_current_score(db, customer_id)


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: int,
    data: CustomerIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_can_access_customer(user, customer_id)
    if user.role == UserRole.CUSTOMER:
        current = customer_services.get_customer(db, customer_id)
        if (
            data.monthly_income != current.monthly_income
            or data.date_of_birth != current.date_of_birth
        ):
            raise HTTPException(
                status_code=403,
                detail="Only an officer can change income or date of birth",
            )
    return customer_services.update_customer(db, customer_id, data)

@router.delete("/{customer_id}", response_model=MessageOut, status_code=200, dependencies=officer_only,)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer_services.delete_customer(db, customer_id)
    return {"message": "Customer deleted successfully"}


@router.get("/{customer_id}/summary", response_model=CustomerSummaryOut)
def customer_summary(customer_id: int, db: Session = Depends(get_db),user: User = Depends(get_current_user),):
    ensure_can_access_customer(user, customer_id)
    return loan_services.get_customer_summary(db, customer_id)





@router.get("/{customer_id}/eligibility", response_model=EligibilityOut)
def customer_eligibility(
    customer_id: int,
    amount: Decimal = Query(ge=10000, le=5000000),
    tenure_months: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Would this customer be eligible for this loan? Lists every failed rule and what
    could change the outcome. Reads only; no loan is created."""
    ensure_can_access_customer(user, customer_id)
    if tenure_months is not None and tenure_months not in loan_services.INTEREST_RATES:
        raise InvalidInputError("Tenure must be 12, 24, 36, 48 or 60 months")
    return eligibility_advice.report_for_customer(db, customer_id, amount, tenure_months)


@router.get("/{customer_id}/credit-score", response_model=CreditScoreOut)
def credit_score_breakdown(
    customer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_can_access_customer(user, customer_id)
    return customer_services.get_credit_score_breakdown(db, customer_id)


@router.get("/{customer_id}/loans", response_model=list[LoanOut])
def customer_loans(
    customer_id: int, 
    status: str | None = None, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_user),
    ):
    ensure_can_access_customer(user, customer_id)
    return loan_services.list_loans_for_customer(db, customer_id, status)