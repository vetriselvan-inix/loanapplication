"""Checks of the prescreen_loan tool and its access limits. No model, database or password
needed: the loan application is simulated (the same one the graph tests use)."""

import sys

from prescreen_tool import make_prescreen_tool
from test_prescreen_graph import USERS, fake_app

from api_tools import OWN_ACCOUNT_ONLY
from app_client import SESSION_EXPIRED, AppSession

sys.stdout.reconfigure(encoding="utf-8")


def login(username, **kw):
    requests = []
    session = AppSession(base_url="http://app", transport=fake_app(requests, **kw))
    session.login(username, USERS[username][0])
    tool = make_prescreen_tool(session)
    requests.clear()  # forget the login calls
    return tool, requests


def paths(requests):
    return [r.url.path for r in requests]


# ---------- a customer ----------
def test_a_customer_is_screened_for_their_own_account_without_giving_an_id():
    tool, requests = login("hydra")  # hydra is customer 1

    out = tool.invoke({"amount": 500000, "tenure_months": 36})

    assert out["customer_id"] == 1 and out["decision"] == "approve"
    assert out["credit_score"] == 820 and out["emi_percent_of_income"] == 19.5
    assert set(paths(requests)) == {"/customers/1", "/customers/1/summary", "/customers/1/eligibility"}


def test_a_customer_cannot_screen_another_customer_and_no_request_is_sent():
    tool, requests = login("hydra")

    assert tool.invoke({"amount": 500000, "tenure_months": 36, "customer_id": 2}) == OWN_ACCOUNT_ONLY
    assert paths(requests) == []


# ---------- an officer ----------
def test_an_officer_can_screen_any_customer_and_gets_the_graphs_decision():
    tool, _ = login("vetri")

    assert tool.invoke({"amount": 1200000, "tenure_months": 60, "customer_id": 2})["decision"] == "refer"
    assert tool.invoke({"amount": 700000, "tenure_months": 24, "customer_id": 3})["decision"] == "reject"


def test_an_officer_must_say_which_customer():
    tool, requests = login("vetri")

    assert tool.invoke({"amount": 500000, "tenure_months": 36}) == "Please tell me which customer id."
    assert paths(requests) == []


# ---------- what the graph decides ----------
def test_a_missing_amount_or_tenure_is_a_need_info_decision_not_an_error():
    tool, _ = login("hydra")

    out = tool.invoke({})

    assert out["decision"] == "need_info"
    assert "amount is missing" in out["reason"] and "tenure is missing" in out["reason"]


def test_the_reason_and_failed_rules_reach_the_assistant():
    tool, _ = login("vetri")

    out = tool.invoke({"amount": 450000, "tenure_months": 36, "customer_id": 4})

    assert out["decision"] == "reject" and len(out["failed_rules"]) == 2
    assert "Rejected:" in out["reason"]


def test_an_unknown_customer_gets_the_apps_own_message_in_the_reason():
    tool, _ = login("vetri")

    out = tool.invoke({"amount": 300000, "tenure_months": 24, "customer_id": 999})

    assert out["decision"] == "need_info" and "Customer 999 not found" in out["reason"]


# ---------- a login that ran out, and privacy ----------
def test_an_expired_login_gives_a_message_instead_of_a_decision():
    tool, _ = login("hydra", expire_after=1)

    assert tool.invoke({"amount": 300000, "tenure_months": 24}) == SESSION_EXPIRED


def test_the_assistant_never_gets_email_phone_or_date_of_birth():
    tool, _ = login("hydra")

    text = str(tool.invoke({"amount": 500000, "tenure_months": 36})).lower()

    for private in ("email", "phone", "date_of_birth", "x@example.com", "9000000000", "1990-01-01"):
        assert private not in text


# ---------- what the model is told ----------
def test_the_prompt_tells_the_model_when_to_use_the_tool():
    from loan_agent import system_prompt

    session = AppSession(base_url="http://app", transport=fake_app([]))
    session.login("hydra", USERS["hydra"][0])

    assert "prescreen_loan" in system_prompt(session)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
