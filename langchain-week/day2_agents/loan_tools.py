"""Read-only tools that let the agent look at the loan application's real data.

The connection is opened in Postgres read-only mode, so nothing here can change a row.
Rules and calculations come from the app's own code, so the answers match the app.
"""

import functools
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from langchain.tools import tool
from loan_application.repositories import customer_repositories, loan_repositories
from calc_tools import compare_tenures, emi_calculator, get_interest_rate, tenure_rows  # noqa: F401  (re-exported)
from loan_application.services import credit_score, loan_services
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_engine = create_engine(
    os.environ["LOAN_DB_URL"],
    connect_args={"options": "-c default_transaction_read_only=on"},
)


def _session() -> Session:
    return Session(_engine)


def _number(value: Decimal) -> float:
    return float(value)


DATABASE_DOWN = "I cannot reach the loan database right now. Please make sure it is running and try again."


def _handles_database_down(func):
    """Return a friendly message instead of crashing the agent when the database is unreachable."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OperationalError:
            return DATABASE_DOWN

    return wrapper


@tool
@_handles_database_down
def get_customer(customer_id: int) -> dict | str:
    """Look up one customer of the loan application by their numeric customer id.
    Returns the customer's name, age, monthly income in rupees, existing monthly EMI
    in rupees (sum of their approved loans), number of approved loans, risk band and
    credit score (300 to 850, calculated by the system) together with how that score is
    made up: base 300 plus income points, EMI points and age points.
    Returns a short message if the id is invalid or the customer does not exist."""
    if customer_id <= 0:
        return "Customer id must be a positive whole number, for example 29."
    with _session() as db:
        customer = customer_repositories.get_by_id(db, customer_id)
        if customer is None:
            return f"Customer {customer_id} was not found."
        summary = loan_services.get_customer_summary(db, customer_id)
        today = datetime.now().astimezone().date()
        # Worked out now, like check_eligibility, so the two tools never disagree
        score = credit_score.current_breakdown(db, customer)
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "age": loan_services.calculate_age(customer.date_of_birth, today),
            "monthly_income": _number(customer.monthly_income),
            "existing_monthly_emi": _number(summary["total_monthly_emi"]),
            "approved_loans": summary["approved_count"],
            "risk_band": summary["risk_band"],
            "credit_score": score["score"],
            "credit_score_breakdown": {
                "base": score["base"],
                "income_points": score["income_points"],
                "emi_points": score["emi_points"],
                "age_points": score["age_points"],
                "emi_percent_of_income": score["emi_percent_of_income"],
                "minimum_required": score["minimum_required"],
            },
        }


@tool
@_handles_database_down
def check_eligibility(customer_id: int, amount: float) -> dict | str:
    """Check whether a customer is eligible for a loan of the given amount in rupees.
    Checks every rule: age between 21 and 60, amount at most 20 times monthly income,
    fewer than 2 approved loans, and a credit score of at least 600. Returns eligible
    (true or false), the list of ALL failed rules, the credit score (300 to 850) and the
    highest amount their income allows. Does not apply for a loan.
    Returns a short message if the customer id or amount is invalid or not found."""
    if customer_id <= 0:
        return "Customer id must be a positive whole number, for example 29."
    if amount <= 0:
        return "Loan amount must be greater than zero."
    with _session() as db:
        customer = customer_repositories.get_by_id(db, customer_id)
        if customer is None:
            return f"Customer {customer_id} was not found."
        today = datetime.now().astimezone().date()
        age = loan_services.calculate_age(customer.date_of_birth, today)
        approved = loan_repositories.count_approved_for_customer(db, customer_id)
        limit = 20 * customer.monthly_income
        reasons = []
        # Thresholds and wording are copied from loan_services.check_eligibility,
        # which stops at the first failure; this lists every failure.
        if not (21 <= age <= 60):
            reasons.append("Age must be between 21 and 60")
        if Decimal(str(amount)) > limit:
            reasons.append("Requested amount exceeds 20x monthly income")
        if approved >= 2:
            reasons.append("Customer already has 2 active loans")
        # current_score only reads, so it is safe on this read-only connection
        score = credit_score.current_score(db, customer)
        if score < credit_score.MIN_APPROVAL_SCORE:
            reasons.append(f"Credit score must be at least {credit_score.MIN_APPROVAL_SCORE}")
        return {
            "customer_id": customer_id,
            "amount": amount,
            "credit_score": score,
            "eligible": not reasons,
            "failed_rules": reasons,
            "max_amount_by_income": _number(limit),
        }
