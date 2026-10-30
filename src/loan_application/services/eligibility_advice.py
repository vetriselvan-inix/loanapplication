from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from loan_application.repositories import loan_repositories
from loan_application.services import credit_score, customer_services, loan_services
from loan_application.tables import Customer


def rupees(value: Decimal) -> str:
    """Whole rupees with Indian grouping, for example 1000000 becomes Rs 10,00,000."""
    digits = str(int(value))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "Rs " + ",".join(groups + [tail])


def _advice_for(rule: str, fixable: bool, suggestion: str) -> dict:
    return {"rule": rule, "fixable": fixable, "suggestion": suggestion}


def eligibility_report(
    db: Session, customer: Customer, amount: Decimal, tenure_months: int | None = None
) -> dict:
    """Every rule the request fails, the credit score, and what could change the outcome.
    Reads only; nothing is saved."""
    age = loan_services.calculate_age(
        customer.date_of_birth, datetime.now().astimezone().date()
    )
    income = customer.monthly_income
    existing_emi = Decimal(loan_repositories.summary_for_customer(db, customer.id)[4] or 0)
    score = credit_score.score_breakdown(income, age, existing_emi)
    failed = loan_services.failed_rules(db, customer, amount)
    max_by_income = loan_services.INCOME_MULTIPLE * income
    minimum = credit_score.MIN_APPROVAL_SCORE

    advice = []
    if loan_services.AGE_REASON in failed:
        advice.append(
            _advice_for(
                loan_services.AGE_REASON,
                False,
                f"Applicants must be {loan_services.MIN_AGE} to {loan_services.MAX_AGE} "
                f"years old and this customer is {age}. Changing the request cannot fix this.",
            )
        )
    if loan_services.INCOME_REASON in failed:
        advice.append(
            _advice_for(
                loan_services.INCOME_REASON,
                True,
                f"Ask for at most {rupees(max_by_income)}, which is "
                f"{loan_services.INCOME_MULTIPLE} times the monthly income of {rupees(income)}.",
            )
        )
    if loan_services.LOANS_REASON in failed:
        advice.append(
            _advice_for(
                loan_services.LOANS_REASON,
                False,
                "A new loan cannot be approved while a customer has "
                f"{loan_services.MAX_ACTIVE_LOANS} active loans. Changing the request cannot fix this.",
            )
        )
    if loan_services.SCORE_REASON in failed:
        limit = credit_score.max_emi_for_minimum(income, age)
        if limit is None:
            advice.append(
                _advice_for(
                    loan_services.SCORE_REASON,
                    False,
                    f"Even with no existing EMI the score would stay below {minimum}, because "
                    "income and age give too few points. A higher income would be needed.",
                )
            )
        else:
            advice.append(
                _advice_for(
                    loan_services.SCORE_REASON,
                    True,
                    f"Existing monthly EMIs are {rupees(existing_emi)}. They would need to fall to "
                    f"{rupees(limit)} or less (a drop of about {rupees(existing_emi - limit)}) "
                    f"for the score to reach {minimum}.",
                )
            )

    projection = None
    if tenure_months in loan_services.INTEREST_RATES:
        rate = loan_services.INTEREST_RATES[tenure_months]
        new_emi = loan_services.calculate_emi(amount, rate, tenure_months)
        after = credit_score.score_breakdown(income, age, existing_emi + new_emi)
        projection = {
            "tenure_months": tenure_months,
            "annual_rate_percent": float(rate),
            "new_emi": float(new_emi),
            "total_emi_after": float(existing_emi + new_emi),
            "score_after_loan": after["score"],
            "stays_above_minimum": after["meets_minimum"],
        }
        if not failed and not after["meets_minimum"]:
            advice.append(
                _advice_for(
                    "After this loan",
                    True,
                    f"The customer qualifies now, but with this loan's EMI of {rupees(new_emi)} "
                    f"the credit score would fall to {after['score']}, below {minimum}, so a "
                    "further application would be refused. A smaller amount or a longer tenure "
                    "keeps the score higher.",
                )
            )

    return {
        "customer_id": customer.id,
        "amount": float(amount),
        "eligible": not failed,
        "failed_rules": failed,
        "credit_score": score["score"],
        "minimum_score": minimum,
        "max_amount_by_income": float(max_by_income),
        "advice": advice,
        "projection": projection,
    }


def report_for_customer(
    db: Session, customer_id: int, amount: Decimal, tenure_months: int | None = None
) -> dict:
    customer = customer_services.get_customer(db, customer_id)
    return eligibility_report(db, customer, amount, tenure_months)
