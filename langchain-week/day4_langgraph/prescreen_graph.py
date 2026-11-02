"""Day 4 assignment: the Loan Pre-Screening Graph.

An email and a customer id go in; a decision (approve, refer, reject or need_info), a plain
reason and a log of the boxes visited come out. The path is fixed by the code, and only the
first box (intake) uses the model. It reads real customers through the loan application as
the logged-in user, so an officer can screen anyone and a customer only their own account.

Run:  uv run python day4_langgraph\\prescreen_graph.py     (writes graph.md, the diagram)
"""

import operator
import sys
from decimal import Decimal
from pathlib import Path
from typing import Annotated, NotRequired, TypedDict

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "day1_langchain"))
sys.path.insert(0, str(HERE.parent / "day2_agents"))
from app_client import CANNOT_REACH, SESSION_EXPIRED, AppError, AppSession  # noqa: E402
from calc_tools import MAX_LOAN, MIN_LOAN  # noqa: E402
from enquiry_reader import LoanEnquiry, read_enquiry  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from loan_application.services import loan_services  # noqa: E402
from loan_application.services.eligibility_advice import rupees  # noqa: E402

BURDEN_LIMIT = Decimal(50)  # the guide's policy 1.4: every EMI including the new one, as a percent of income
REFER_ABOVE_AMOUNT = Decimal(1_000_000)  # policy 2.3 (in both policy files): above this an officer must look at it
MIN_SCORE_FOR_REFERRAL = 550  # below this score the graph rejects
APPROVE_FROM_SCORE = 600  # the app's own minimum; 550 to 599 is referred to an officer instead

DECISIONS = ("approve", "refer", "reject", "need_info")


class State(TypedDict):
    email: str
    customer_id: int
    log: Annotated[list[str], operator.add]  # every box adds its own name
    enquiry: NotRequired[LoanEnquiry]
    amount: NotRequired[float]  # only set once the amount is present and valid
    tenure_months: NotRequired[int]  # only set once the tenure is present and valid
    customer: NotRequired[dict]  # just what the checks need: no email, phone or date of birth
    problems: NotRequired[list[str]]
    emi: NotRequired[float]
    burden_percent: NotRequired[float]
    credit_score: NotRequired[int]
    failed_rules: NotRequired[list[str]]
    decision: NotRequired[str]
    reason: NotRequired[str]


def route(state: State) -> str:
    """The diamond. The order is the priority: missing information, then failed rules, then
    anything that needs a person's eye, otherwise approve."""
    if state.get("problems"):
        return "need_info"
    if state.get("failed_rules"):
        return "reject"
    if state.get("credit_score", 0) < APPROVE_FROM_SCORE or state.get("amount", 0) > REFER_ABOVE_AMOUNT:
        return "refer"
    return "approve"


def approve(state: State):
    reason = (
        f"Approved. It passes every rule: credit score {state.get('credit_score')}, and the EMI of "
        f"{rupees(Decimal(str(state.get('emi', 0))))} would be {state.get('burden_percent')}% of monthly income."
    )
    return {"decision": "approve", "reason": reason, "log": ["approve"]}


def refer(state: State):
    why = []
    if state.get("credit_score", 0) < APPROVE_FROM_SCORE:
        why.append(
            f"the credit score {state.get('credit_score')} is between {MIN_SCORE_FOR_REFERRAL} and "
            f"{APPROVE_FROM_SCORE - 1}, below the app's minimum of {APPROVE_FROM_SCORE}"
        )
    if state.get("amount", 0) > REFER_ABOVE_AMOUNT:
        why.append(f"the amount is above {rupees(REFER_ABOVE_AMOUNT)}")
    return {
        "decision": "refer",
        "reason": "Referred to an officer: " + " and ".join(why) + ".",
        "log": ["refer"],
    }


def reject(state: State):
    return {
        "decision": "reject",
        "reason": "Rejected: " + "; ".join(state.get("failed_rules", [])) + ".",
        "log": ["reject"],
    }


def need_info(state: State):
    return {
        "decision": "need_info",
        "reason": "More information needed: " + "; ".join(state.get("problems", [])) + ".",
        "log": ["need_info"],
    }


def build_graph(session: AppSession, reader=read_enquiry):
    """The graph, tied to one login. The reader is a parameter so the tests can run without a model."""

    def intake(state: State):
        return {"enquiry": reader(state["email"]), "log": ["intake"]}

    def validate(state: State):
        enquiry = state.get("enquiry")
        amount = enquiry.amount if enquiry else None
        tenure = enquiry.tenure_months if enquiry else None
        problems = []
        update: dict = {"log": ["validate"]}
        if amount is None:
            problems.append("The loan amount is missing")
        elif not MIN_LOAN <= Decimal(str(amount)) <= MAX_LOAN:
            problems.append(f"The amount must be between {rupees(MIN_LOAN)} and {rupees(MAX_LOAN)}")
        else:
            update["amount"] = amount
        if tenure is None:
            problems.append("The tenure is missing")
        elif tenure not in loan_services.INTEREST_RATES:
            problems.append("The tenure must be 12, 24, 36, 48 or 60 months")
        else:
            update["tenure_months"] = tenure
        try:
            found = session.get(f"/customers/{state['customer_id']}")
            update["customer"] = {
                "id": found["id"],
                "name": found["name"],
                "monthly_income": float(found["monthly_income"]),
            }
        except AppError as problem:
            if str(problem) in (CANNOT_REACH, SESSION_EXPIRED):
                raise  # the app is out of reach: that is not a reason to say need_info
            problems.append(str(problem))  # not found, or not allowed for this login
        update["problems"] = problems
        return update

    def score(state: State):
        amount, tenure, customer = state.get("amount"), state.get("tenure_months"), state.get("customer")
        if amount is None or tenure is None or customer is None:
            return {"log": ["score (skipped)"]}  # something is missing, so there is nothing to score
        rate = loan_services.INTEREST_RATES[tenure]
        emi = loan_services.calculate_emi(Decimal(str(amount)), rate, tenure)
        summary = session.get(f"/customers/{customer['id']}/summary")
        income = Decimal(str(customer["monthly_income"]))
        burden = (Decimal(str(summary["total_monthly_emi"])) + emi) / income * 100
        eligibility = session.get(
            f"/customers/{customer['id']}/eligibility", amount=amount, tenure_months=tenure
        )
        # The app's own rules, all of them, except its score rule: the graph judges the score
        # itself (below 550 reject, 550 to 599 refer), so the app's "at least 600" is left out
        failed = [rule for rule in eligibility["failed_rules"] if rule != loan_services.SCORE_REASON]
        if eligibility["credit_score"] < MIN_SCORE_FOR_REFERRAL:
            failed.append(
                f"Credit score {eligibility['credit_score']} is below {MIN_SCORE_FOR_REFERRAL}, "
                "the lowest score that can still be referred"
            )
        if burden > BURDEN_LIMIT:
            failed.append(
                f"Total EMIs including the new loan would be {burden:.1f}% of monthly income "
                f"(the limit is {BURDEN_LIMIT}%)"
            )
        return {
            "emi": float(emi),
            "burden_percent": round(float(burden), 1),
            "credit_score": eligibility["credit_score"],
            "failed_rules": failed,
            "log": ["score"],
        }

    builder = StateGraph(State)
    builder.add_node("intake", intake)
    builder.add_node("validate", validate)
    builder.add_node("score", score)
    for name, fn in (("approve", approve), ("refer", refer), ("reject", reject), ("need_info", need_info)):
        builder.add_node(name, fn)
        builder.add_edge(name, END)
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "validate")
    builder.add_edge("validate", "score")
    builder.add_conditional_edges("score", route, {name: name for name in DECISIONS})
    return builder.compile()


def prescreen(graph, email: str, customer_id: int) -> dict:
    """Run one email through the graph. The result is the final state as a plain dict."""
    return graph.invoke({"email": email, "customer_id": customer_id, "log": []})


if __name__ == "__main__":
    diagram = build_graph(AppSession()).get_graph().draw_mermaid()  # drawing needs no login
    path = HERE / "graph.md"
    path.write_text(f"# Loan pre-screening graph\n\n```mermaid\n{diagram}```\n", encoding="utf-8")
    print(diagram)
    print(f"written: {path}")
