from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from loan_application.repositories import loan_repositories
from loan_application.tables import Customer

MIN_SCORE = 300
MAX_SCORE = 850
MIN_APPROVAL_SCORE = 600

INCOME_MAX_POINTS = 200
INCOME_FULL_POINTS_AT = Decimal(100000)  # monthly income that earns the full points
EMI_MAX_POINTS = 250
AGE_BEST_POINTS = 100
AGE_OK_POINTS = 60


def _age(dob: date, today: date) -> int:
    # Same rule as loan_services.calculate_age, which cannot be imported here
    # because loan_services imports this module.
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _age_points(age: int) -> int:
    if 25 <= age <= 55:
        return AGE_BEST_POINTS
    if 21 <= age <= 60:
        return AGE_OK_POINTS
    return 0


def compute_credit_score(
    monthly_income: Decimal, age: int, existing_emi: Decimal
) -> int:
    """Score from 300 to 850: base 300, plus income, EMI burden and age points.

    Only approved loans count (through existing_emi), so a rejection never lowers a score.
    """
    income_points = min(
        Decimal(INCOME_MAX_POINTS),
        monthly_income / INCOME_FULL_POINTS_AT * INCOME_MAX_POINTS,
    )
    burden = min(existing_emi / monthly_income, Decimal(1))
    emi_points = EMI_MAX_POINTS * (1 - burden)

    score = MIN_SCORE + income_points + emi_points + _age_points(age)
    score = int(score.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(MIN_SCORE, min(MAX_SCORE, score))


def current_score(db: Session, customer: Customer) -> int:
    """The score from the customer's data right now. Changes nothing, so it is safe
    to call from a check that must not write."""
    if customer.id is None:  # new customer: no loans yet
        existing_emi = Decimal(0)
    else:
        existing_emi = Decimal(
            loan_repositories.summary_for_customer(db, customer.id)[4]
        )
    age = _age(customer.date_of_birth, datetime.now().astimezone().date())
    return compute_credit_score(customer.monthly_income, age, existing_emi)


def refresh_credit_score(db: Session, customer: Customer) -> int:
    """Recalculate and set the customer's stored score. Does not commit; the caller's
    transaction saves it together with the change that triggered it."""
    customer.credit_score = current_score(db, customer)
    return customer.credit_score
