"""Checks of the pre-screening graph. No model, database or password needed: the email reader
and the loan application are both simulated."""

import sys

import httpx
from prescreen_graph import build_graph, prescreen

from app_client import SESSION_EXPIRED, AppError, AppSession
from enquiry_reader import LoanEnquiry

sys.stdout.reconfigure(encoding="utf-8")

USERS = {"vetri": ("pw-vetri", "OFFICER", None), "hydra": ("pw-hydra", "CUSTOMER", 1)}
# income, credit score, existing EMI: the first four are the shapes of the real test customers
CUSTOMERS = {
    1: {"name": "Test Approve", "income": 85000, "score": 820, "emi": 0},
    2: {"name": "Test Refer Amount", "income": 60000, "score": 770, "emi": 0},
    3: {"name": "Test Reject Burden", "income": 40000, "score": 730, "emi": 0},
    4: {"name": "Test Approve Score 650", "income": 20000, "score": 650, "emi": 0},
    5: {"name": "Test Refer Low Score", "income": 20000, "score": 575, "emi": 5979},
    7: {"name": "Test Reject Score", "income": 20000, "score": 546, "emi": 8304},
    8: {"name": "Edge 550", "income": 20000, "score": 550, "emi": 0},
    9: {"name": "Edge 549", "income": 20000, "score": 549, "emi": 0},
}


def fake_app(requests, expire_after=None):
    """The loan application as far as the graph uses it, with the app's own rules for the
    amount and the score. Every request is recorded."""
    served = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path == "/auth/login":
            form = dict(pair.split("=", 1) for pair in request.content.decode().split("&"))
            entry = USERS.get(form["username"])
            if entry is None or entry[0] != form["password"]:
                return httpx.Response(401, json={"detail": "Invalid credentials"})
            return httpx.Response(200, json={"access_token": "token-" + form["username"]})
        username = request.headers.get("authorization", "").removeprefix("Bearer token-")
        _, role, own = USERS[username]
        served["n"] += 1
        if expire_after is not None and served["n"] > expire_after:
            return httpx.Response(401, json={"detail": "expired"})
        if path == "/auth/me":
            return httpx.Response(200, json={"username": username, "role": role, "customer_id": own})
        parts = path.strip("/").split("/")  # customers, id, [what]
        customer_id = int(parts[1])
        if role == "CUSTOMER" and customer_id != own:
            return httpx.Response(403, json={"detail": "Not allowed to access this resource"})
        c = CUSTOMERS.get(customer_id)
        if c is None:
            return httpx.Response(404, json={"error": "NOT_FOUND", "message": f"Customer {customer_id} not found"})
        what = parts[2] if len(parts) > 2 else ""
        if what == "":
            return httpx.Response(200, json={"id": customer_id, "name": c["name"], "email": "x@example.com",
                                             "phone": "9000000000", "date_of_birth": "1990-01-01",
                                             "monthly_income": str(c["income"]), "credit_score": c["score"]})
        if what == "summary":
            return httpx.Response(200, json={"total_monthly_emi": c["emi"], "approved_count": 1 if c["emi"] else 0,
                                             "risk_band": "LOW"})
        if what == "eligibility":
            amount = float(request.url.params["amount"])
            failed = []
            if amount > 20 * c["income"]:
                failed.append("Requested amount exceeds 20x monthly income")
            if c["score"] < 600:
                failed.append("Credit score must be at least 600")
            return httpx.Response(200, json={"customer_id": customer_id, "eligible": not failed,
                                             "failed_rules": failed, "credit_score": c["score"],
                                             "minimum_score": 600})
        return httpx.Response(404, json={"message": "Not found"})

    return httpx.MockTransport(handler)


def reading(amount, tenure):
    """A reader that returns this enquiry for any email."""
    return lambda email: LoanEnquiry(
        customer_name=None, amount=amount, tenure_months=tenure, purpose=None, confidence="high", error=None
    )


def screen(customer_id, amount, tenure, user="vetri", **kw):
    requests = []
    session = AppSession(base_url="http://app", transport=fake_app(requests, **kw))
    session.login(user, USERS[user][0])
    graph = build_graph(session, reader=reading(amount, tenure))
    requests.clear()  # forget the login calls
    return prescreen(graph, "an email", customer_id), requests


def paths(requests):
    return [r.url.path for r in requests]


# ---------- the four decisions ----------
def test_a_strong_customer_is_approved_and_the_log_shows_the_path():
    out, _ = screen(1, 500000, 36)

    assert out["decision"] == "approve"
    assert out["log"] == ["intake", "validate", "score", "approve"]
    assert out["credit_score"] == 820 and out["burden_percent"] == 19.5
    assert 16600 < out["emi"] < 16610  # 5 lakh, 36 months, the app's 12%


def test_an_amount_above_ten_lakh_is_referred():
    out, _ = screen(2, 1200000, 60)

    assert out["decision"] == "refer" and "Rs 10,00,000" in out["reason"]
    assert out["log"][-1] == "refer"


def test_a_score_from_550_to_599_is_referred_even_though_the_app_would_refuse_it():
    out, _ = screen(5, 100000, 36)  # the app's own score rule fails here; the graph does not use it

    assert out["decision"] == "refer" and "575" in out["reason"]
    assert out["failed_rules"] == []


def test_a_score_of_600_or_more_is_approved():
    out, _ = screen(4, 250000, 36)  # score 650, in the old 650 to 699 refer band

    assert out["decision"] == "approve"


def test_the_edges_of_the_refer_band():
    assert screen(8, 100000, 36)[0]["decision"] == "refer"  # 550 is the lowest score that is referred
    assert screen(9, 100000, 36)[0]["decision"] == "reject"  # 549 is rejected


def test_a_burden_over_fifty_percent_is_rejected_even_with_a_good_score():
    out, _ = screen(3, 700000, 24)

    assert out["decision"] == "reject" and out["credit_score"] == 730
    assert out["burden_percent"] == 81.6 and "81.6%" in out["reason"]
    assert len(out["failed_rules"]) == 1  # only the burden rule


def test_a_score_below_550_is_rejected_on_its_own():
    out, _ = screen(7, 10000, 60)  # a small loan, so the burden stays fine

    assert out["decision"] == "reject"
    assert out["failed_rules"] == ["Credit score 546 is below 550, the lowest score that can still be referred"]
    assert out["burden_percent"] < 50


def test_every_failed_rule_is_listed():
    out, _ = screen(4, 450000, 36)  # above 20x income and too big an EMI

    assert out["decision"] == "reject" and len(out["failed_rules"]) == 2
    assert "20x" in out["reason"] and "% of monthly income" in out["reason"]


# ---------- need_info ----------
def test_a_missing_amount_and_tenure_need_info_and_the_app_is_not_asked_to_score():
    out, requests = screen(1, None, None)

    assert out["decision"] == "need_info"
    assert "amount is missing" in out["reason"] and "tenure is missing" in out["reason"]
    assert out["log"] == ["intake", "validate", "score (skipped)", "need_info"]
    assert paths(requests) == ["/customers/1"]  # no summary, no eligibility


def test_an_unknown_customer_needs_info_with_the_apps_own_message():
    out, _ = screen(999, 300000, 24)

    assert out["decision"] == "need_info" and "Customer 999 not found" in out["reason"]


def test_a_tenure_the_app_does_not_offer_needs_info():
    out, _ = screen(1, 300000, 30)

    assert out["decision"] == "need_info" and "12, 24, 36, 48 or 60" in out["reason"]


def test_an_amount_outside_the_apps_limits_needs_info():
    out, _ = screen(1, 5000, 12)

    assert out["decision"] == "need_info" and "must be between" in out["reason"]


# ---------- the login ----------
def test_a_customer_cannot_screen_another_customer():
    out, _ = screen(2, 300000, 24, user="hydra")

    assert out["decision"] == "need_info" and "not allowed" in out["reason"]
    assert "customer" not in out  # nothing about customer 2 was kept


def test_a_customer_can_screen_their_own_account():
    out, _ = screen(1, 300000, 24, user="hydra")

    assert out["decision"] == "approve"


def test_an_expired_login_stops_the_graph_instead_of_inventing_a_decision():
    try:
        screen(1, 300000, 24, expire_after=1)  # the first call after login is the customer fetch
    except AppError as problem:
        assert str(problem) == SESSION_EXPIRED
    else:
        raise AssertionError("an expired login should stop the graph")


# ---------- what the state keeps ----------
def test_the_state_keeps_no_email_phone_or_date_of_birth():
    out, _ = screen(1, 500000, 36)

    assert set(out["customer"]) == {"id", "name", "monthly_income"}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
