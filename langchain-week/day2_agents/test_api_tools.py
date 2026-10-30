"""Checks of the customer tools and their access limits. No app, database or model needed:
the loan application is simulated, including its rule that a customer's token can only reach
their own record."""

import sys

import httpx
from api_tools import OWN_ACCOUNT_ONLY, make_api_tools
from app_client import NOT_ALLOWED, SESSION_EXPIRED, AppSession

sys.stdout.reconfigure(encoding="utf-8")

USERS = {
    "hydra": ("pw-hydra", "CUSTOMER", 29),
    "kamal": ("pw-kamal", "CUSTOMER", 27),
    "vetri": ("pw-vetri", "OFFICER", None),
}
CUSTOMERS = {
    29: {"id": 29, "name": "hydra", "email": "hydra@example.com", "phone": "9000000029",
         "date_of_birth": "2004-05-01", "monthly_income": "50000.00", "credit_score": 710},
    27: {"id": 27, "name": "kamal", "email": "kamal@example.com", "phone": "9000000027",
         "date_of_birth": "2006-10-15", "monthly_income": "50000.00", "credit_score": 650},
    11: {"id": 11, "name": "raj", "email": "raj@example.com", "phone": "9000000011",
         "date_of_birth": "2002-10-08", "monthly_income": "36000.00", "credit_score": 607},
}


def fake_app(requests, expire_after=None, bad_amount=False):
    """The loan application as far as these tools use it. Every request is recorded."""
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
        auth = request.headers.get("authorization", "")
        username = auth.removeprefix("Bearer token-") if auth.startswith("Bearer token-") else None
        if username not in USERS:
            return httpx.Response(401, json={"detail": "Could not validate credentials"})
        served["n"] += 1
        if expire_after is not None and served["n"] > expire_after:
            return httpx.Response(401, json={"detail": "expired"})
        _, role, own = USERS[username]
        if path == "/auth/me":
            return httpx.Response(200, json={"username": username, "role": role, "customer_id": own})
        parts = path.strip("/").split("/")  # customers, id, [what]
        customer_id = int(parts[1])
        if role == "CUSTOMER" and customer_id != own:
            return httpx.Response(403, json={"detail": "Not allowed to access this resource"})
        if customer_id not in CUSTOMERS:
            return httpx.Response(404, json={"error": "NOT_FOUND", "message": f"Customer {customer_id} not found"})
        what = parts[2] if len(parts) > 2 else ""
        if what == "":
            return httpx.Response(200, json=CUSTOMERS[customer_id])
        if what == "summary":
            return httpx.Response(200, json={"total_monthly_emi": 10843.45, "approved_count": 2, "risk_band": "MEDIUM"})
        if what == "credit-score":
            return httpx.Response(200, json={"score": CUSTOMERS[customer_id]["credit_score"], "base": 300,
                                             "income_points": 100.0, "emi_points": 250.0, "age_points": 60.0,
                                             "emi_percent_of_income": 0.0, "minimum_required": 600})
        if what == "eligibility":
            if bad_amount:
                return httpx.Response(400, json={"error": "VALIDATION_FAILED", "message": "Invalid input",
                                                 "details": [{"field": "amount",
                                                              "message": "Input should be greater than or equal to 10000"}]})
            return httpx.Response(200, json={"customer_id": customer_id, "eligible": True, "failed_rules": [],
                                             "amount": float(request.url.params["amount"]), "advice": []})
        return httpx.Response(404, json={"message": "Not found"})

    return httpx.MockTransport(handler)


def login(username, **kw):
    requests = []
    session = AppSession(base_url="http://app", transport=fake_app(requests, **kw))
    session.login(username, USERS[username][0])
    tools = {t.name: t for t in make_api_tools(session)}
    requests.clear()  # forget the login calls; the tests look at what the tools ask for
    return session, tools, requests


def paths(requests):
    return [r.url.path for r in requests]


# ---------- a customer ----------
def test_a_customer_is_shown_their_own_account_without_giving_an_id():
    session, tools, requests = login("hydra")

    out = tools["get_customer"].invoke({})

    assert out["customer_id"] == 29 and out["name"] == "hydra"
    assert out["credit_score"] == 710 and out["credit_score_breakdown"]["income_points"] == 100.0
    assert paths(requests) == ["/customers/29", "/customers/29/summary", "/customers/29/credit-score"]


def test_the_assistant_never_gets_email_phone_or_date_of_birth():
    _, tools, _ = login("hydra")

    text = str(tools["get_customer"].invoke({})).lower()

    for private in ("email", "phone", "date_of_birth", "hydra@example.com", "9000000029", "2004-05-01"):
        assert private not in text


def test_a_customer_asking_for_their_own_id_is_fine():
    _, tools, requests = login("hydra")

    assert tools["get_customer"].invoke({"customer_id": 29})["customer_id"] == 29
    assert set(paths(requests)) == {"/customers/29", "/customers/29/summary", "/customers/29/credit-score"}


def test_a_customer_cannot_look_at_another_customer_and_no_request_is_even_sent():
    _, tools, requests = login("hydra")

    assert tools["get_customer"].invoke({"customer_id": 11}) == OWN_ACCOUNT_ONLY
    assert tools["check_eligibility"].invoke({"amount": 100000, "customer_id": 27}) == OWN_ACCOUNT_ONLY
    assert paths(requests) == []


def test_a_customer_checks_eligibility_for_their_own_account():
    _, tools, requests = login("hydra")

    out = tools["check_eligibility"].invoke({"amount": 500000, "tenure_months": 36})

    assert out["eligible"] is True and out["customer_id"] == 29
    assert paths(requests) == ["/customers/29/eligibility"]
    assert float(requests[0].url.params["amount"]) == 500000
    assert requests[0].url.params["tenure_months"] == "36"


def test_the_app_refuses_even_if_the_code_check_were_bypassed():
    # Pretend the role is wrong in memory: the app checks the token again and says no
    session, tools, requests = login("hydra")
    session.role = "OFFICER"

    assert tools["get_customer"].invoke({"customer_id": 11}) == NOT_ALLOWED
    assert paths(requests) == ["/customers/11"]  # the app was asked, and refused


# ---------- an officer ----------
def test_an_officer_can_look_at_any_customer():
    _, tools, _ = login("vetri")

    assert tools["get_customer"].invoke({"customer_id": 11})["name"] == "raj"
    assert tools["check_eligibility"].invoke({"amount": 100000, "customer_id": 29})["eligible"] is True


def test_an_officer_must_say_which_customer():
    _, tools, requests = login("vetri")

    assert tools["get_customer"].invoke({}) == "Please tell me which customer id."
    assert "positive whole number" in tools["get_customer"].invoke({"customer_id": 0})
    assert paths(requests) == []


def test_an_unknown_customer_gets_the_apps_own_message():
    _, tools, _ = login("vetri")

    assert tools["get_customer"].invoke({"customer_id": 999}) == "Customer 999 not found"


# ---------- bad input and a login that ran out ----------
def test_a_bad_amount_is_refused_before_asking_the_app():
    _, tools, requests = login("hydra")

    assert tools["check_eligibility"].invoke({"amount": 0}) == "Loan amount must be greater than zero."
    assert paths(requests) == []


def test_the_apps_reason_for_rejecting_input_reaches_the_user():
    _, tools, _ = login("hydra", bad_amount=True)

    out = tools["check_eligibility"].invoke({"amount": 5000})

    assert "amount: Input should be greater than or equal to 10000" in out


def test_an_expired_login_gives_a_message_and_logs_out():
    session, tools, _ = login("hydra", expire_after=1)  # call 1 was /auth/me during login

    assert tools["get_customer"].invoke({}) == SESSION_EXPIRED
    assert not session.logged_in
    assert tools["get_customer"].invoke({}) == "Please log in first."


# ---------- what the model is told ----------
def test_the_prompt_tells_each_role_what_it_may_do():
    from loan_agent import system_prompt

    customer, _, _ = login("hydra")
    officer, _, _ = login("vetri")

    assert "CUSTOMER (customer 29)" in system_prompt(customer)
    assert "never ask for a customer id" in system_prompt(customer)
    assert "OFFICER (vetri)" in system_prompt(officer)
    assert "any customer" in system_prompt(officer)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
