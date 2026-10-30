"""The customer tools, going through the loan application as the logged-in user.

make_api_tools(session) builds the tools for ONE login. The identity lives in the session
the program holds, not in anything the model can write, and the app checks every request
again with the user's token, so a customer can only ever reach their own account and an
officer can reach any. The model never sees the token, and these tools never read the
database.
"""

from datetime import date, datetime

from app_client import AppError, AppSession
from langchain.tools import tool

OWN_ACCOUNT_ONLY = "You can only ask about your own account."


def _age(date_of_birth: str) -> int:
    born = date.fromisoformat(date_of_birth)
    today = datetime.now().astimezone().date()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def make_api_tools(session: AppSession) -> list:
    def resolve(customer_id: int | None) -> int:
        """The customer id to ask the app about, or an AppError saying why the user may not."""
        if not session.logged_in:
            raise AppError("Please log in first.")
        if session.role == "CUSTOMER":
            if customer_id in (None, session.customer_id):
                return session.customer_id
            raise AppError(OWN_ACCOUNT_ONLY)  # the app would also refuse; no request is sent
        if customer_id is None:
            raise AppError("Please tell me which customer id.")
        if customer_id <= 0:
            raise AppError("Customer id must be a positive whole number, for example 29.")
        return customer_id

    @tool
    def get_customer(customer_id: int | None = None) -> dict | str:
        """Look up a customer of the loan application. A customer is always shown their own
        account, so they should leave customer_id empty; an officer must give the numeric
        customer id. Returns the customer's name, age, monthly income in rupees, existing
        monthly EMI in rupees (sum of their approved loans), number of approved loans, risk
        band and credit score (300 to 850, calculated by the system) with how it is made up:
        base 300 plus income points, EMI points and age points. Returns a short message if
        the user is not allowed to see that customer or the customer does not exist."""
        try:
            cid = resolve(customer_id)
            customer = session.get(f"/customers/{cid}")
            summary = session.get(f"/customers/{cid}/summary")
            score = session.get(f"/customers/{cid}/credit-score")
        except AppError as problem:
            return str(problem)
        # Only what the assistant needs: no email, phone number or date of birth
        return {
            "customer_id": customer["id"],
            "name": customer["name"],
            "age": _age(customer["date_of_birth"]),
            "monthly_income": float(customer["monthly_income"]),
            "existing_monthly_emi": summary["total_monthly_emi"],
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
    def check_eligibility(
        amount: float, tenure_months: int | None = None, customer_id: int | None = None
    ) -> dict | str:
        """Check whether a customer is eligible for a loan of the given amount in rupees.
        A customer is always checked for their own account, so they should leave customer_id
        empty; an officer must give the numeric customer id. tenure_months (12, 24, 36, 48
        or 60) is optional and adds a projection of the credit score after the loan. Checks
        every rule: age between 21 and 60, amount at most 20 times monthly income, fewer than
        2 approved loans, and a credit score of at least 600. Returns eligible (true or
        false), ALL failed rules, the credit score, the highest amount their income allows,
        advice on what could change the outcome, and the projection. Does not apply for a
        loan. Returns a short message if the user is not allowed or the input is invalid."""
        if amount <= 0:
            return "Loan amount must be greater than zero."
        try:
            cid = resolve(customer_id)
            return session.get(
                f"/customers/{cid}/eligibility", amount=amount, tenure_months=tenure_months
            )
        except AppError as problem:
            return str(problem)

    return [get_customer, check_eligibility]
