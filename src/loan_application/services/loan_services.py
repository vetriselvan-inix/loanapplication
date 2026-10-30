from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from loan_application.exceptions import (
    CustomerNotFound,
    InvalidInputError,
    NotFoundError,
)
from loan_application.repositories import customer_repositories, loan_repositories
from loan_application.schemas.loan_schemas import LoanApplyIn
from loan_application.tables import Customer, Loan, User, UserRole

VALID_STATUSES = {"APPROVED", "REJECTED"}
from loan_application.services import credit_score, customer_services
from loan_application.services.transaction import transaction

INTEREST_RATES = {
    12: Decimal(10),
    24: Decimal(11),
    36: Decimal(12),
    48: Decimal(13),
    60: Decimal(13),
}


def calculate_age(dob: date, today: date) -> int:
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def calculate_emi(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    r = annual_rate / Decimal(12) / Decimal(100)
    factor = (1 + r) ** months
    emi = principal * r * factor / (factor - 1)
    return emi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


MIN_AGE = 21
MAX_AGE = 60
INCOME_MULTIPLE = 20  # the amount may be at most this many times the monthly income
MAX_ACTIVE_LOANS = 2

AGE_REASON = f"Age must be between {MIN_AGE} and {MAX_AGE}"
INCOME_REASON = f"Requested amount exceeds {INCOME_MULTIPLE}x monthly income"
LOANS_REASON = f"Customer already has {MAX_ACTIVE_LOANS} active loans"
SCORE_REASON = f"Credit score must be at least {credit_score.MIN_APPROVAL_SCORE}"


def failed_rules(db: Session, customer: Customer, amount: Decimal) -> list[str]:
    """Every eligibility rule the request fails, in the order the rules are checked."""
    failed = []
    age = calculate_age(customer.date_of_birth, datetime.now().astimezone().date())
    if not (MIN_AGE <= age <= MAX_AGE):
        failed.append(AGE_REASON)

    if amount > INCOME_MULTIPLE * customer.monthly_income:
        failed.append(INCOME_REASON)

    if loan_repositories.count_approved_for_customer(db, customer.id) >= MAX_ACTIVE_LOANS:
        failed.append(LOANS_REASON)

    # Worked out fresh, not read from the stored column, so it is never stale
    if credit_score.current_score(db, customer) < credit_score.MIN_APPROVAL_SCORE:
        failed.append(SCORE_REASON)

    return failed


def check_eligibility(db: Session, customer: Customer, amount: Decimal) -> str | None:
    """Return the rejection reason of the first failed rule, or None if eligible."""
    failed = failed_rules(db, customer, amount)
    return failed[0] if failed else None


def apply_for_loan(db: Session, data: LoanApplyIn) -> Loan:
    customer = customer_repositories.get_by_id(db, data.customer_id)
    if customer is None:
        raise CustomerNotFound(data.customer_id)

    reason = check_eligibility(db, customer, data.amount)

    if reason:
        loan = Loan(
            customer_id=customer.id,
            amount=data.amount,
            tenure_months=data.tenure_months,
            status="REJECTED",
            rejection_reason=reason,
        )
    else:
        rate = INTEREST_RATES[data.tenure_months]
        loan = Loan(
            customer_id=customer.id,
            amount=data.amount,
            tenure_months=data.tenure_months,
            interest_rate=rate,
            emi=calculate_emi(data.amount, rate, data.tenure_months),
            status="APPROVED",
        )

    with transaction(db):
        loan_repositories.add(db, loan)
        credit_score.refresh_credit_score(db, customer)
    db.refresh(loan)
    return loan


def get_loan(db: Session, loan_id: int) -> Loan:
    if loan_id <= 0: 
        raise InvalidInputError("id must be a positive integer")
    loan = loan_repositories.get_by_id(db, loan_id)
    if loan is None:
        raise NotFoundError(f"Loan {loan_id} not found")
    return loan


def risk_band(ratio: Decimal) -> str:
    if ratio < 30:
        return "LOW"
    if ratio <= 50:
        return "MEDIUM"
    return "HIGH"


def get_customer_summary(db: Session, customer_id: int) -> dict:
    customer = customer_repositories.get_by_id(db, customer_id)
    if customer is None:
        raise CustomerNotFound(customer_id)

    total, approved, rejected, approved_amount, approved_emi = (
        loan_repositories.summary_for_customer(db, customer_id)
    )
    approved_amount = Decimal(approved_amount)
    approved_emi = Decimal(approved_emi or 0)

    if customer.monthly_income > 0:
        ratio = (approved_emi / customer.monthly_income * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        ratio = Decimal("0.00")

    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "total_applications": total,
        "approved_count": approved,
        "rejected_count": rejected,
        "total_approved_amount": approved_amount,
        "total_monthly_emi": approved_emi,
        "emi_to_income_ratio": ratio,
        "risk_band": risk_band(ratio),
    }


def approve_loan(db: Session, loan_id: int) -> Loan:
    loan = loan_repositories.get_by_id(db, loan_id)

    if loan is None:
        raise NotFoundError("Loan not found")

    if loan.status == "APPROVED":
        return loan

    customer = customer_repositories.get_by_id(db, loan.customer_id)
    if customer is None:
        raise CustomerNotFound(loan.customer_id)

    reason = check_eligibility(db, customer, loan.amount)
    if reason:
        raise InvalidInputError(f"Cannot approve loan: {reason}")

    rate = INTEREST_RATES[loan.tenure_months]
    with transaction(db):
        loan.interest_rate = rate
        loan.emi = calculate_emi(
            loan.amount,
            rate,
            loan.tenure_months,
        )
        loan.status = "APPROVED"
        loan.rejection_reason = None
        credit_score.refresh_credit_score(db, customer)
    db.refresh(loan)
    return loan


def patch_loan(db: Session, loan_id: int) -> Loan:
    loan = loan_repositories.get_by_id(db, loan_id)

    if loan is None:
        raise NotFoundError("Loan not found")

    with transaction(db):
        loan.status = "REJECTED"
        loan.interest_rate = None
        loan.emi = None
        loan.rejection_reason = "Rejected by administrator"
        customer = customer_repositories.get_by_id(db, loan.customer_id)
        if customer is not None:
            credit_score.refresh_credit_score(db, customer)
    db.refresh(loan)
    return loan


def delete_loan(db: Session, loan_id: int) -> None:
    loan = loan_repositories.get_by_id(db, loan_id)

    if loan is None:
        raise NotFoundError("Loan not found")

    customer = customer_repositories.get_by_id(db, loan.customer_id)
    with transaction(db):
        loan_repositories.delete(db, loan)
        if customer is not None:
            credit_score.refresh_credit_score(db, customer)


def normalize_status(status: str | None) -> str | None:
    """Uppercase the status filter and reject anything but APPROVED/REJECTED."""
    if status is None:
        return None
    status = status.upper()
    if status not in VALID_STATUSES:
        raise InvalidInputError("Status must be APPROVED or REJECTED")
    return status


def list_loans_page(
    db: Session, user: User, status: str | None, page: int, size: int
) -> dict:
    """A page of loans the user may see: officers see all, customers only their own."""
    status = normalize_status(status)
    customer_id = None if user.role == UserRole.OFFICER else user.customer_id

    items, total = loan_repositories.list_page(
        db, customer_id, status, offset=(page - 1) * size, limit=size
    )
    total_pages = -(-total // size)  # ceiling division: 25 loans / 10 per page = 3
    return {
        "items": items,
        "page": page,
        "size": size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def list_loans_for_customer(
    db: Session,
    customer_id: int,
    status: str | None = None,
) -> list[Loan]:
    if customer_id <= 0:
        raise InvalidInputError("id must be a positive integer")
    customer = customer_repositories.get_by_id(db, customer_id)

    if customer is None:
        raise CustomerNotFound(customer_id)

    status = normalize_status(status)

    return loan_repositories.list_for_customer(
        db,
        customer_id,
        status,
    )






def list_customer_loans(db: Session, customer_id: int, status: str | None = None):
    if status is not None and status not in VALID_STATUSES:
        raise InvalidInputError("status must be APPROVED or REJECTED")

    customer_services.get_customer(db, customer_id)  # raises 400 or 404
    return loan_repositories.list_by_customer(db, customer_id, status)
