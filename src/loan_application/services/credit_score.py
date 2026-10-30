from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

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


def _points(monthly_income: Decimal, age: int, existing_emi: Decimal):
    """The three parts of the score, before rounding, and the EMI burden they came from."""
    income_points = min(
        Decimal(INCOME_MAX_POINTS),
        monthly_income / INCOME_FULL_POINTS_AT * INCOME_MAX_POINTS,
    )
    burden = min(existing_emi / monthly_income, Decimal(1))
    emi_points = EMI_MAX_POINTS * (1 - burden)
    return income_points, emi_points, Decimal(_age_points(age)), burden


def compute_credit_score(
    monthly_income: Decimal, age: int, existing_emi: Decimal
) -> int:
    """Score from 300 to 850: base 300, plus income, EMI burden and age points.

    Only approved loans count (through existing_emi), so a rejection never lowers a score.
    """
    income_points, emi_points, age_points, _ = _points(
        monthly_income, age, existing_emi
    )
    score = MIN_SCORE + income_points + emi_points + age_points
    score = int(score.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(MIN_SCORE, min(MAX_SCORE, score))


def _one_decimal(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def score_breakdown(monthly_income: Decimal, age: int, existing_emi: Decimal) -> dict:
    """The score and where it came from. The parts are shown to one decimal; the score is
    the rounded total of the unrounded parts, so the shown parts can differ from it by 0.1."""
    income_points, emi_points, age_points, _ = _points(
        monthly_income, age, existing_emi
    )
    score = compute_credit_score(monthly_income, age, existing_emi)
    return {
        "score": score,
        "base": MIN_SCORE,
        "income_points": _one_decimal(income_points),
        "emi_points": _one_decimal(emi_points),
        "age_points": _one_decimal(age_points),
        "existing_emi": float(existing_emi),
        "emi_percent_of_income": _one_decimal(
            existing_emi / monthly_income * 100
        ),  # the real share, not capped at 100
        "minimum_required": MIN_APPROVAL_SCORE,
        "meets_minimum": score >= MIN_APPROVAL_SCORE,
    }


def max_emi_for_minimum(monthly_income: Decimal, age: int) -> Decimal | None:
    """The highest total monthly EMI at which the score still reaches the approval minimum,
    in whole rupees. None if even with no EMI at all the score would stay below it."""
    income_points, _, age_points, _ = _points(monthly_income, age, Decimal(0))
    best_score = MIN_SCORE + income_points + EMI_MAX_POINTS + age_points
    # The score is rounded half up, so the exact total only has to reach the minimum less 0.5
    room = best_score - (MIN_APPROVAL_SCORE - Decimal("0.5"))
    if room < 0:
        return None
    return (room / EMI_MAX_POINTS * monthly_income).quantize(
        Decimal(1), rounding=ROUND_DOWN
    )


def _inputs(db: Session, customer: Customer) -> tuple[Decimal, int, Decimal]:
    """Income, age and total approved EMI of the customer as they are right now."""
    if customer.id is None:  # new customer: no loans yet
        existing_emi = Decimal(0)
    else:
        existing_emi = Decimal(
            loan_repositories.summary_for_customer(db, customer.id)[4]
        )
    age = _age(customer.date_of_birth, datetime.now().astimezone().date())
    return customer.monthly_income, age, existing_emi


def current_score(db: Session, customer: Customer) -> int:
    """The score from the customer's data right now. Changes nothing, so it is safe
    to call from a check that must not write."""
    return compute_credit_score(*_inputs(db, customer))


def current_breakdown(db: Session, customer: Customer) -> dict:
    """The score breakdown from the customer's data right now. Changes nothing."""
    return score_breakdown(*_inputs(db, customer))


def refresh_credit_score(db: Session, customer: Customer) -> int:
    """Recalculate and set the customer's stored score. Does not commit; the caller's
    transaction saves it together with the change that triggered it."""
    customer.credit_score = current_score(db, customer)
    return customer.credit_score
