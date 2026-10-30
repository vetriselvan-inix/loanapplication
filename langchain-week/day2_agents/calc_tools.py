"""Tools that only calculate. They need no database and no login, so they work for everyone.

Rates and the EMI formula come from the app's own code, so the answers match the app.
"""

from decimal import Decimal

from langchain.tools import tool
from loan_application.services import loan_services


def _number(value: Decimal) -> float:
    return float(value)


@tool
def emi_calculator(principal: float, annual_rate_percent: float, months: int) -> dict | str:
    """Calculate the monthly EMI of a loan. principal is the loan amount in rupees,
    annual_rate_percent is the yearly interest rate in percent (for example 12 for 12%),
    months is the tenure in months. Returns the EMI, total payment and total interest
    in rupees. Returns a short message if any input is zero, negative or unreasonable."""
    if principal <= 0:
        return "Loan amount must be greater than zero."
    if annual_rate_percent <= 0 or annual_rate_percent > 100:
        return "Interest rate must be above 0 and at most 100 percent per year."
    if months <= 0:
        return "Tenure must be a positive number of months."
    emi = loan_services.calculate_emi(
        Decimal(str(principal)), Decimal(str(annual_rate_percent)), months
    )
    total = emi * months
    return {
        "emi": _number(emi),
        "total_payment": _number(total),
        "total_interest": _number(total - Decimal(str(principal))),
    }


@tool
def get_interest_rate(tenure_months: int) -> str:
    """Return the annual interest rate in percent that the loan application charges
    for a loan tenure given in months. Valid tenures are 12, 24, 36, 48 and 60.
    Returns a short message if the tenure is not one of those."""
    rate = loan_services.INTEREST_RATES.get(tenure_months)
    if rate is None:
        return "Tenure must be 12, 24, 36, 48 or 60 months."
    return f"{rate}% per year for {tenure_months} months."


# The loan amount limits of the app (see check_amount in tables.py and LoanApplyIn)
MIN_LOAN = Decimal(10_000)
MAX_LOAN = Decimal(5_000_000)


def tenure_rows(amount: Decimal, monthly_income: Decimal | None = None) -> list[dict]:
    """One row per tenure the app offers: its own rate, the EMI, and what the loan costs in all."""
    rows = []
    for months in sorted(loan_services.INTEREST_RATES):
        rate = loan_services.INTEREST_RATES[months]
        emi = loan_services.calculate_emi(amount, rate, months)
        total = emi * months
        row = {
            "tenure_months": months,
            "annual_rate_percent": _number(rate),
            "emi": _number(emi),
            "total_payment": _number(total),
            "total_interest": _number(total - amount),
        }
        if monthly_income:
            row["emi_percent_of_income"] = round(_number(emi / monthly_income * 100), 1)
        rows.append(row)
    return rows


@tool
def compare_tenures(amount: float, monthly_income: float | None = None) -> dict | str:
    """Compare every tenure the application offers (12, 24, 36, 48 and 60 months) for one
    loan amount in rupees. For each tenure it gives that tenure's interest rate, the monthly
    EMI, the total payment and the total interest. If monthly_income is given, it also gives
    the EMI as a percent of that income. Use it when someone asks which tenure to choose or
    wants tenures side by side. Returns a short message if the amount is outside 10,000 to
    50,00,000 or the income is not above zero."""
    if not MIN_LOAN <= Decimal(str(amount)) <= MAX_LOAN:
        return "Loan amount must be between Rs 10,000 and Rs 50,00,000."
    if monthly_income is not None and monthly_income <= 0:
        return "Monthly income must be greater than zero."
    income = Decimal(str(monthly_income)) if monthly_income is not None else None
    return {"amount": amount, "options": tenure_rows(Decimal(str(amount)), income)}
