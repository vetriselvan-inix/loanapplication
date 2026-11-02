"""The pre-screening graph as a tool, so the chat assistant can run it.

The agent decides WHEN to call it; the graph decides HOW, with its fixed steps and rules.
The agent has already read the amount and tenure from the user's message, so the graph's
email-reading box is given them directly instead of calling the model a second time.
The tool is tied to one login, like the other customer tools: a customer is always screened
for their own account, and an officer must name the customer.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day1_langchain"))
sys.path.insert(0, str(HERE.parent / "day2_agents"))
from api_tools import resolve_customer  # noqa: E402
from app_client import AppError, AppSession  # noqa: E402
from enquiry_reader import LoanEnquiry  # noqa: E402
from langchain.tools import tool  # noqa: E402
from prescreen_graph import build_graph, prescreen  # noqa: E402


def make_prescreen_tool(session: AppSession):
    @tool
    def prescreen_loan(
        amount: float | None = None, tenure_months: int | None = None, customer_id: int | None = None
    ) -> dict | str:
        """Pre-screen a loan for a customer and give a decision: approve, refer (an officer
        must review it), reject (with every failed rule) or need_info (something is missing).
        Use it when the user asks whether a loan of a given amount and tenure would be
        approved, or asks for a decision. amount is in rupees; tenure_months is 12, 24, 36, 48
        or 60. If the user has not given the amount or the tenure, leave it empty and the
        result will say what is missing. A customer is always screened for their own account,
        so they should leave customer_id empty; an officer must give the numeric customer id.
        Returns the decision, the reason, the credit score, the EMI and the share of monthly
        income that all EMIs would take. It only pre-screens: it does not apply for the loan.
        Returns a short message if the user is not allowed to see that customer."""
        try:
            cid = resolve_customer(session, customer_id)
            enquiry = LoanEnquiry(
                customer_name=None, amount=amount, tenure_months=tenure_months,
                purpose=None, confidence="high", error=None,
            )
            graph = build_graph(session, reader=lambda email: enquiry)
            state = prescreen(graph, "", cid)
        except AppError as problem:  # not allowed, or the login ran out, or the app is down
            return str(problem)
        return {
            "customer_id": cid,
            "decision": state["decision"],
            "reason": state["reason"],
            "credit_score": state.get("credit_score"),
            "emi": state.get("emi"),
            "emi_percent_of_income": state.get("burden_percent"),
            "failed_rules": state.get("failed_rules", []),
        }

    return prescreen_loan
